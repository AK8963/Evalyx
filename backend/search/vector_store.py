"""
Vector store abstraction.

Tries Qdrant if available; falls back to a simple in-process cosine-similarity
store so the app runs without any extra infrastructure.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process fallback (no deps)
# ---------------------------------------------------------------------------

class _InMemoryStore:
    """Flat cosine-similarity search over stored vectors."""

    def __init__(self) -> None:
        # {collection: {id: (vector, payload)}}
        self._store: Dict[str, Dict[str, Tuple[List[float], Dict]]] = {}

    def upsert(self, collection: str, doc_id: str, vector: List[float], payload: Dict) -> None:
        self._store.setdefault(collection, {})[doc_id] = (vector, payload)

    def search(self, collection: str, query_vector: List[float], top_k: int = 10) -> List[Dict]:
        store = self._store.get(collection, {})
        if not store:
            return []

        def cosine(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            return dot / (na * nb + 1e-10)

        scored = [
            {"id": doc_id, "score": cosine(query_vector, vec), "payload": payload}
            for doc_id, (vec, payload) in store.items()
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete(self, collection: str, doc_id: str) -> None:
        self._store.get(collection, {}).pop(doc_id, None)

    def count(self, collection: str) -> int:
        return len(self._store.get(collection, {}))


# ---------------------------------------------------------------------------
# Qdrant backend
# ---------------------------------------------------------------------------

class _QdrantStore:
    def __init__(self, url: str) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._client = QdrantClient(url=url)
        self._Distance = Distance
        self._VectorParams = VectorParams
        self._created: set = set()

    def _ensure_collection(self, collection: str, dim: int = 384) -> None:
        if collection in self._created:
            return
        from qdrant_client.models import Distance, VectorParams
        try:
            self._client.get_collection(collection)
        except Exception:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        self._created.add(collection)

    def upsert(self, collection: str, doc_id: str, vector: List[float], payload: Dict) -> None:
        from qdrant_client.models import PointStruct
        self._ensure_collection(collection, dim=len(vector))
        self._client.upsert(
            collection_name=collection,
            points=[PointStruct(id=_str_to_uint(doc_id), vector=vector, payload=payload)],
        )

    def search(self, collection: str, query_vector: List[float], top_k: int = 10) -> List[Dict]:
        try:
            self._ensure_collection(collection, dim=len(query_vector))
            hits = self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=top_k,
            )
            return [{"id": str(h.id), "score": h.score, "payload": h.payload} for h in hits]
        except Exception as exc:
            logger.warning("Qdrant search failed: %s", exc)
            return []

    def delete(self, collection: str, doc_id: str) -> None:
        from qdrant_client.models import PointIdsList
        try:
            self._client.delete(
                collection_name=collection,
                points_selector=PointIdsList(points=[_str_to_uint(doc_id)]),
            )
        except Exception:
            pass

    def count(self, collection: str) -> int:
        try:
            return self._client.count(collection_name=collection).count
        except Exception:
            return 0


def _str_to_uint(s: str) -> int:
    """Map a UUID string to a uint64 for Qdrant point IDs."""
    import hashlib
    digest = hashlib.sha256(s.encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2 ** 63)


# ---------------------------------------------------------------------------
# Public singleton
# ---------------------------------------------------------------------------

def get_vector_store(qdrant_url: Optional[str] = None):
    """
    Return the best available vector store.
    Tries Qdrant first; falls back to in-process store.
    """
    if qdrant_url:
        try:
            store = _QdrantStore(url=qdrant_url)
            logger.info("Using Qdrant vector store at %s", qdrant_url)
            return store
        except Exception as exc:
            logger.warning("Qdrant unavailable (%s). Using in-memory store.", exc)

    logger.info("Using in-memory vector store (no persistence)")
    return _InMemoryStore()
