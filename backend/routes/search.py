"""
Search routes — semantic + keyword search over traces.
"""



from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Trace, User

router = APIRouter()


@router.get("/semantic")
def semantic_search(
    project_id: str,
    q: str = Query(..., min_length=2),
    top_k: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic (embedding-based) search over indexed traces.
    Falls back to keyword search if embeddings are unavailable.
    """
    from backend.search.semantic_search import get_search_engine

    engine = get_search_engine()
    hits = engine.search(q, project_id=project_id, top_k=top_k)

    if hits:
        # Enrich with DB fields
        trace_ids = [h["trace_id"] for h in hits]
        traces_by_id = {
            t.id: t
            for t in db.query(Trace).filter(Trace.id.in_(trace_ids), Trace.project_id == project_id).all()
        }
        results = []
        for h in hits:
            t = traces_by_id.get(h["trace_id"])
            if t:
                results.append({
                    "trace_id": t.id,
                    "score": h["score"],
                    "model": t.model,
                    "status": t.status,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "latency_ms": t.latency_ms,
                })
        return {"results": results, "method": "semantic", "total": len(results)}

    # Keyword fallback
    return keyword_search(project_id=project_id, q=q, limit=top_k, db=db, current_user=current_user)


@router.get("/keyword")
def keyword_search(
    project_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full-text keyword search (PostgreSQL ILIKE)."""
    pattern = f"%{q}%"
    traces = (
        db.query(Trace)
        .filter(
            Trace.project_id == project_id,
            or_(
                Trace.model.ilike(pattern),
                Trace.status.ilike(pattern),
                Trace.error_message.ilike(pattern),
            ),
        )
        .order_by(Trace.timestamp.desc())
        .limit(limit)
        .all()
    )

    results = [
        {
            "trace_id": t.id,
            "score": 1.0,
            "model": t.model,
            "status": t.status,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "latency_ms": t.latency_ms,
        }
        for t in traces
    ]
    return {"results": results, "method": "keyword", "total": len(results)}


@router.post("/index/{trace_id}")
def index_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger embedding indexing for a single trace."""
    from backend.search.semantic_search import get_search_engine

    trace = db.query(Trace).filter_by(id=trace_id).first()
    if not trace:
        from fastapi import HTTPException
        raise HTTPException(404, "Trace not found")

    indexed = get_search_engine().index_trace(trace)
    return {"indexed": indexed, "trace_id": trace_id}
