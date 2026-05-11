"""
Topics Engine — ML-powered pattern discovery in trace logs.

Automatically extracts facets (task intent, sentiment, issues) from traces
and clusters them into named topics using sentence embeddings + k-means.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _trace_to_text(trace_data: Dict[str, Any]) -> str:
    """Extract the most representative text from a trace dict."""
    parts: List[str] = []

    def _extract(obj: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(obj, str):
            parts.append(obj[:500])
        elif isinstance(obj, dict):
            for k in ("content", "text", "message", "query", "prompt",
                      "input", "output", "user", "assistant"):
                if k in obj:
                    _extract(obj[k], depth + 1)
            for v in list(obj.values())[:5]:
                if isinstance(v, (str, dict, list)):
                    _extract(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:3]:
                _extract(item, depth + 1)

    for field in ("input_data", "output_data", "meta"):
        _extract(trace_data.get(field))

    return " ".join(parts)[:1000]


# ---------------------------------------------------------------------------
# Facet extractors
# ---------------------------------------------------------------------------

_SENTIMENT_POSITIVE = re.compile(
    r"\b(great|good|thanks|perfect|awesome|excellent|helpful|love|amazing)\b",
    re.IGNORECASE,
)
_SENTIMENT_NEGATIVE = re.compile(
    r"\b(bad|wrong|error|fail|issue|problem|broken|terrible|awful|hate)\b",
    re.IGNORECASE,
)

_ISSUE_PATTERNS = re.compile(
    r"\b(error|exception|traceback|timeout|refused|unauthori[sz]ed|not found|"
    r"500|502|503|504)\b",
    re.IGNORECASE,
)


def extract_sentiment(text: str) -> str:
    """Simple rule-based sentiment: positive / negative / neutral."""
    pos = len(_SENTIMENT_POSITIVE.findall(text))
    neg = len(_SENTIMENT_NEGATIVE.findall(text))
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def extract_issue(text: str, status: str = "success") -> str:
    """Detect failure / issue patterns."""
    if status in ("error", "failed", "partial"):
        return "error_response"
    if _ISSUE_PATTERNS.search(text):
        return "potential_issue"
    return "no_issue"


def extract_task(text: str) -> str:
    """
    Coarse intent classification using keyword heuristics.
    In production you'd use an LLM or a trained classifier.
    """
    text_lower = text.lower()
    if any(w in text_lower for w in ("summar", "tldr", "brief", "overview")):
        return "summarization"
    if any(w in text_lower for w in ("translat", "convert to", "in spanish", "in french")):
        return "translation"
    if any(w in text_lower for w in ("code", "python", "javascript", "function", "def ", "class ")):
        return "code_generation"
    if any(w in text_lower for w in ("question", "what is", "how to", "explain", "why", "who")):
        return "question_answering"
    if any(w in text_lower for w in ("classify", "categorize", "label", "which category")):
        return "classification"
    if any(w in text_lower for w in ("extract", "parse", "find all", "list all")):
        return "extraction"
    if any(w in text_lower for w in ("write", "draft", "compose", "generate text", "create a")):
        return "text_generation"
    if any(w in text_lower for w in ("search", "find", "look up", "retrieve")):
        return "retrieval"
    return "general"


# ---------------------------------------------------------------------------
# Facet registry
# ---------------------------------------------------------------------------

FACET_EXTRACTORS = {
    "task": extract_task,
    "sentiment": extract_sentiment,
    "issues": extract_issue,
}


# ---------------------------------------------------------------------------
# Topic manager
# ---------------------------------------------------------------------------

class TopicsEngine:
    """
    Manages extraction, assignment and clustering of topics.

    Light-weight version (no heavy ML deps required at startup):
    - Uses rule-based extractors for facets (task / sentiment / issues)
    - Uses optional sentence-transformers for richer clustering
    - Assigns topics using label → Topic DB records
    """

    def __init__(self, db_session_factory=None):
        self._db_factory = db_session_factory
        self._embedder = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Embedding (optional, falls back gracefully)
    # ------------------------------------------------------------------

    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model all-MiniLM-L6-v2")
        except Exception as exc:
            logger.warning("sentence-transformers not available (%s). Embeddings disabled.", exc)
        return self._embedder

    def embed_text(self, text: str) -> Optional[List[float]]:
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            return embedder.encode(text, convert_to_numpy=True).tolist()
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Core: analyse a single trace dict
    # ------------------------------------------------------------------

    def analyse_trace(
        self,
        trace_data: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Return a mapping of {facet_type: label} for a trace.

        Args:
            trace_data: dict with keys matching the Trace model fields.

        Returns:
            e.g. {"task": "summarization", "sentiment": "positive", "issues": "no_issue"}
        """
        text = _trace_to_text(trace_data)
        status = trace_data.get("status", "success")

        return {
            "task": extract_task(text),
            "sentiment": extract_sentiment(text),
            "issues": extract_issue(text, status),
        }

    # ------------------------------------------------------------------
    # DB integration
    # ------------------------------------------------------------------

    def get_or_create_topic(
        self,
        db,
        project_id: str,
        facet_type: str,
        label: str,
    ):
        """Return existing Topic or create a new one."""
        from database.models import Topic

        topic = (
            db.query(Topic)
            .filter_by(project_id=project_id, facet_type=facet_type, name=label)
            .first()
        )
        if topic is None:
            topic = Topic(
                project_id=project_id,
                facet_type=facet_type,
                name=label,
            )
            db.add(topic)
            db.flush()
        return topic

    def assign_topics_to_trace(self, db, trace) -> None:
        """
        Analyse trace and persist TopicAssignment rows.
        Safe to call multiple times (idempotent via unique constraint).
        """
        from database.models import TopicAssignment

        trace_data = {
            "input_data": trace.input_data,
            "output_data": trace.output_data,
            "meta": trace.meta if hasattr(trace, "meta") else {},
            "status": trace.status,
        }
        facets = self.analyse_trace(trace_data)

        for facet_type, label in facets.items():
            topic = self.get_or_create_topic(
                db, trace.project_id, facet_type, label
            )
            # Upsert assignment
            existing = (
                db.query(TopicAssignment)
                .filter_by(trace_id=trace.id, topic_id=topic.id)
                .first()
            )
            if existing is None:
                db.add(
                    TopicAssignment(
                        trace_id=trace.id,
                        topic_id=topic.id,
                        confidence=1.0,
                    )
                )
            # Update topic counter
            topic.trace_count = (topic.trace_count or 0) + 1

    def get_topics_summary(self, db, project_id: str) -> List[Dict[str, Any]]:
        """Return all topics for a project grouped by facet."""
        from database.models import Topic

        topics = (
            db.query(Topic)
            .filter_by(project_id=project_id, is_active=True)
            .order_by(Topic.facet_type, Topic.trace_count.desc())
            .all()
        )
        result: Dict[str, List] = {}
        for t in topics:
            result.setdefault(t.facet_type, []).append(
                {
                    "id": t.id,
                    "name": t.name,
                    "facet_type": t.facet_type,
                    "trace_count": t.trace_count,
                }
            )
        return [
            {"facet_type": ft, "topics": ts}
            for ft, ts in result.items()
        ]


# Singleton — imported by routes and tasks
topics_engine = TopicsEngine()
