"""
Embedding generation for semantic search.

Falls back gracefully when sentence-transformers is not installed —
full-text keyword search remains available.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is not None:
        return _encoder
    try:
        from sentence_transformers import SentenceTransformer
        _encoder = SentenceTransformer(_MODEL_NAME)
        logger.info("Loaded sentence-transformers encoder: %s", _MODEL_NAME)
    except Exception as exc:
        logger.warning("sentence-transformers unavailable: %s", exc)
    return _encoder


def embed(text: str) -> Optional[List[float]]:
    """Return a float vector for *text*, or None if encoder unavailable."""
    enc = _get_encoder()
    if enc is None:
        return None
    try:
        vec = enc.encode(text, convert_to_numpy=True)
        return vec.tolist()
    except Exception as exc:
        logger.warning("embed() failed: %s", exc)
        return None


def trace_to_text(trace: Any) -> str:
    """
    Convert a Trace ORM object (or dict) to a plain-text string for embedding.
    """
    parts: List[str] = []

    def extract(obj: Any, depth: int = 0) -> None:
        if depth > 4 or not obj:
            return
        if isinstance(obj, str):
            parts.append(obj[:400])
        elif isinstance(obj, dict):
            for k in ("content", "text", "message", "query", "prompt",
                      "input", "output", "user", "assistant", "system"):
                if k in obj:
                    extract(obj[k], depth + 1)
        elif isinstance(obj, list):
            for item in obj[:4]:
                extract(item, depth + 1)

    if hasattr(trace, "input_data"):
        extract(trace.input_data)
        extract(trace.output_data)
    elif isinstance(trace, dict):
        extract(trace.get("input_data"))
        extract(trace.get("output_data"))

    return " ".join(parts)[:1000]


def cache_key(text: str) -> str:
    """Stable SHA-256 key for caching embeddings by content."""
    return hashlib.sha256(text.encode()).hexdigest()
