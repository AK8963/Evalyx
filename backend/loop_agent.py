"""
Loop AI Agent — answers natural-language questions about project logs.

Uses a simple Retrieval-Augmented Generation (RAG) approach:
1. Semantic search for relevant traces.
2. Build a context window from retrieved traces.
3. Call an LLM to synthesise an answer.

Falls back gracefully when no LLM key is configured.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _format_trace(trace, max_chars: int = 400) -> str:
    """Render a Trace ORM object as a compact text block."""
    parts = [
        f"[Trace {trace.id[:8]}]",
        f"model={trace.model or 'unknown'}",
        f"status={trace.status}",
    ]
    if trace.latency_ms:
        parts.append(f"latency={trace.latency_ms:.0f}ms")
    if trace.cost_usd:
        parts.append(f"cost=${float(trace.cost_usd):.4f}")

    def _text(obj: Any) -> str:
        if isinstance(obj, str):
            return obj[:200]
        if isinstance(obj, dict):
            return json.dumps(obj)[:200]
        return str(obj)[:200] if obj else ""

    input_text = _text(trace.input_data)
    output_text = _text(trace.output_data)
    summary = " | ".join(parts)
    if input_text:
        summary += f"\n  INPUT: {input_text}"
    if output_text:
        summary += f"\n  OUTPUT: {output_text}"
    return summary[:max_chars]


def _build_context(traces: List[Any], max_traces: int = 10) -> str:
    """Build an LLM context string from a list of Trace objects."""
    blocks = [_format_trace(t) for t in traces[:max_traces]]
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# SQL-based stats helpers (no LLM required)
# ---------------------------------------------------------------------------

def _stats_answer(db, project_id: str) -> str:
    """Return a quick stats summary for a project."""
    from database.models import Trace, Score
    from sqlalchemy import func

    total = db.query(func.count(Trace.id)).filter(Trace.project_id == project_id).scalar() or 0
    errors = (
        db.query(func.count(Trace.id))
        .filter(Trace.project_id == project_id, Trace.status == "error")
        .scalar() or 0
    )
    avg_lat = (
        db.query(func.avg(Trace.latency_ms))
        .filter(Trace.project_id == project_id, Trace.latency_ms.isnot(None))
        .scalar()
    )
    avg_cost = (
        db.query(func.avg(Trace.cost_usd))
        .filter(Trace.project_id == project_id, Trace.cost_usd.isnot(None))
        .scalar()
    )

    lines = [
        f"**Project stats:**",
        f"- Total traces: {total:,}",
        f"- Error traces: {errors:,} ({100*errors/max(total,1):.1f}%)",
        f"- Avg latency: {avg_lat:.0f} ms" if avg_lat else "- Avg latency: n/a",
        f"- Avg cost: ${float(avg_cost):.4f}" if avg_cost else "- Avg cost: n/a",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm(
    question: str,
    context: str,
    api_key: Optional[str] = None,
    model: str = "gpt-3.5-turbo",
    anthropic_key: Optional[str] = None,
) -> Optional[str]:
    """
    Send a RAG prompt to an LLM and return the answer.
    Tries OpenAI first, then Anthropic, then returns None.
    """
    system_prompt = (
        "You are Loop, an AI assistant embedded in a TraceIQ AI observability platform. "
        "You help engineering and product teams understand their AI application's logs. "
        "Answer concisely using only the trace data provided. "
        "If you cannot answer from the context, say so honestly."
    )
    user_prompt = (
        f"Here are relevant traces from this project:\n\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )

    # --- OpenAI ---
    if api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=512,
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("OpenAI Loop call failed: %s", exc)

    # --- Anthropic ---
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return resp.content[0].text.strip()
        except Exception as exc:
            logger.warning("Anthropic Loop call failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class LoopAgent:
    """
    Orchestrates RAG-based Q&A over a project's traces.
    """

    def __init__(self) -> None:
        from backend.search.semantic_search import get_search_engine
        self._search = get_search_engine()

    def ask(
        self,
        question: str,
        project_id: str,
        db,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        top_k: int = 8,
    ) -> Dict[str, Any]:
        """
        Answer a natural-language question about a project's traces.

        Returns:
            {
              "answer": str,
              "sources": [{"trace_id": str, "score": float}, ...],
              "method": "llm" | "stats" | "fallback"
            }
        """
        question_lower = question.lower()

        # Quick stats questions — no LLM needed
        if any(kw in question_lower for kw in ("how many", "total", "count", "stats", "statistics")):
            answer = _stats_answer(db, project_id)
            return {"answer": answer, "sources": [], "method": "stats"}

        # Semantic retrieval
        hits = self._search.search(question, project_id=project_id, top_k=top_k)
        trace_ids = [h["trace_id"] for h in hits]

        traces: List[Any] = []
        if trace_ids:
            from database.models import Trace
            traces = (
                db.query(Trace)
                .filter(Trace.id.in_(trace_ids), Trace.project_id == project_id)
                .all()
            )

        sources = [{"trace_id": h["trace_id"], "score": h["score"]} for h in hits]

        # If we have traces and an LLM key, generate a real answer
        if traces and (openai_key or anthropic_key):
            context = _build_context(traces)
            answer = _call_llm(
                question, context,
                api_key=openai_key,
                model=model,
                anthropic_key=anthropic_key,
            )
            if answer:
                return {"answer": answer, "sources": sources, "method": "llm"}

        # Fallback: return a textual summary of retrieved traces
        if traces:
            lines = [f"Found {len(traces)} relevant traces:"]
            for t in traces[:5]:
                lines.append(f"- [{t.id[:8]}] {t.model or 'n/a'} | {t.status} | latency {t.latency_ms or '?'}ms")
            return {
                "answer": "\n".join(lines),
                "sources": sources,
                "method": "fallback",
            }

        return {
            "answer": "No relevant traces found for your question. Try asking about specific models, errors, or time periods.",
            "sources": [],
            "method": "fallback",
        }


# Module singleton
loop_agent = LoopAgent()
