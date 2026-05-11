"""
Semantic search engine — hybrid keyword + vector search over traces.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.search.embeddings import embed, trace_to_text
from backend.search.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_COLLECTION = "traces"


class SemanticSearch:
    """Orchestrates embedding generation and vector search."""

    def __init__(self, qdrant_url: Optional[str] = None):
        self._store = get_vector_store(qdrant_url)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_trace(self, trace) -> bool:
        """
        Embed and index a Trace ORM object.
        Returns True if embedding was generated (False if encoder unavailable).
        """
        text = trace_to_text(trace)
        if not text.strip():
            return False

        vec = embed(text)
        if vec is None:
            return False

        payload = {
            "project_id": trace.project_id,
            "model": getattr(trace, "model", None),
            "status": getattr(trace, "status", "success"),
            "timestamp": str(getattr(trace, "timestamp", "")),
        }
        self._store.upsert(_COLLECTION, trace.id, vec, payload)
        return True

    def remove_trace(self, trace_id: str) -> None:
        self._store.delete(_COLLECTION, trace_id)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over indexed traces.

        Args:
            query:      Natural-language search query.
            project_id: Optional project scope filter.
            top_k:      Max number of results.

        Returns:
            List of dicts with 'trace_id', 'score', 'payload'.
        """
        vec = embed(query)
        if vec is None:
            # Fall back: return empty (caller can use SQL keyword search)
            return []

        hits = self._store.search(_COLLECTION, vec, top_k=top_k * 3)

        # Filter by project_id if provided
        if project_id:
            hits = [h for h in hits if h.get("payload", {}).get("project_id") == project_id]

        return [
            {
                "trace_id": h["id"],
                "score": round(h["score"], 4),
                "payload": h.get("payload", {}),
            }
            for h in hits[:top_k]
        ]

    def count_indexed(self) -> int:
        return self._store.count(_COLLECTION)


# ---------------------------------------------------------------------------
# Module-level singleton — created lazily to pick up config at runtime
# ---------------------------------------------------------------------------

_instance: Optional[SemanticSearch] = None


def get_search_engine() -> SemanticSearch:
    global _instance
    if _instance is None:
        try:
            from backend.config import settings
            url = getattr(settings, "QDRANT_URL", None)
        except Exception:
            url = None
        _instance = SemanticSearch(qdrant_url=url)
    return _instance
