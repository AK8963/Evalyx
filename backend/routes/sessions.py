"""
Sessions routes - group traces into named sessions with scoring.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime
from database.models import Session as SessionModel, Trace, Score, Project
from backend.database import get_db
from backend.routes.auth import get_current_user
import uuid
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    trace_ids: Optional[List[str]] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class AddTracesPayload(BaseModel):
    trace_ids: List[str]


class ManualScorePayload(BaseModel):
    manual_score: Optional[float] = None   # not required for llm/from_traces scoring
    scorer_type: Optional[str] = "from_traces"  # "from_traces" | "ollama" | "human"
    model: Optional[str] = "llama2"             # Ollama model (only for scorer_type == "ollama")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_to_dict(s: SessionModel, include_traces: bool = False, db: DBSession = None) -> dict:
    data = {
        "id": s.id,
        "project_id": s.project_id,
        "name": s.name,
        "description": s.description,
        "trace_ids": s.trace_ids or [],
        "trace_count": len(s.trace_ids or []),
        "manual_score": s.manual_score,
        "aggregate_scores": s.aggregate_scores or {},
        "meta": s.meta or {},
        "tags": s.tags or [],
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
    if include_traces and db and s.trace_ids:
        traces = db.query(Trace).filter(Trace.id.in_(s.trace_ids)).all()
        data["traces"] = [
            {
                "id": t.id,
                "model": t.model,
                "status": t.status,
                "latency_ms": t.latency_ms,
                "total_tokens": t.total_tokens,
                "prompt_tokens": t.prompt_tokens,
                "completion_tokens": t.completion_tokens,
                "cost_usd": float(t.cost_usd) if t.cost_usd is not None else None,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in traces
        ]
    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", tags=["sessions"])
async def list_sessions(
    project_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List all sessions for a project, newest first."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = (
        db.query(SessionModel)
        .filter(SessionModel.project_id == project_id)
        .order_by(desc(SessionModel.created_at))
    )
    total = query.count()
    sessions = query.offset(offset).limit(limit).all()

    return {
        "items": [_session_to_dict(s) for s in sessions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201, tags=["sessions"])
async def create_session(
    payload: SessionCreate,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Create a new session."""
    project = db.query(Project).filter(
        Project.id == payload.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate any provided trace_ids belong to this project
    initial_traces = []
    if payload.trace_ids:
        valid = db.query(Trace.id).filter(
            Trace.id.in_(payload.trace_ids),
            Trace.project_id == payload.project_id,
        ).all()
        initial_traces = [r[0] for r in valid]

    session = SessionModel(
        id=str(uuid.uuid4()),
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        meta=payload.meta or {},
        tags=payload.tags or [],
        trace_ids=initial_traces,
        aggregate_scores={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_dict(session)


@router.get("/{session_id}", tags=["sessions"])
async def get_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Get a session with all linked trace summaries."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project = db.query(Project).filter(
        Project.id == session.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    return _session_to_dict(session, include_traces=True, db=db)


@router.put("/{session_id}", tags=["sessions"])
async def update_session(
    session_id: str,
    payload: SessionUpdate,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Update session metadata."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project = db.query(Project).filter(
        Project.id == session.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    if payload.name is not None:
        session.name = payload.name
    if payload.description is not None:
        session.description = payload.description
    if payload.meta is not None:
        session.meta = payload.meta
    if payload.tags is not None:
        session.tags = payload.tags

    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_dict(session)


@router.delete("/{session_id}", status_code=204, tags=["sessions"])
async def delete_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Delete a session (does not delete underlying traces)."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project = db.query(Project).filter(
        Project.id == session.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(session)
    db.commit()


@router.post("/{session_id}/traces", tags=["sessions"])
async def add_traces(
    session_id: str,
    payload: AddTracesPayload,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Add one or more trace IDs to the session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project = db.query(Project).filter(
        Project.id == session.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate trace IDs exist and belong to the same project
    valid_traces = db.query(Trace.id).filter(
        Trace.id.in_(payload.trace_ids),
        Trace.project_id == session.project_id,
    ).all()
    valid_ids = {row.id for row in valid_traces}

    invalid = [tid for tid in payload.trace_ids if tid not in valid_ids]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Trace IDs not found in this project: {invalid[:5]}",
        )

    existing = set(session.trace_ids or [])
    new_ids = existing | set(payload.trace_ids)
    session.trace_ids = list(new_ids)
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_dict(session)


@router.delete("/{session_id}/traces/{trace_id}", tags=["sessions"])
async def remove_trace(
    session_id: str,
    trace_id: str,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Remove a trace from a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project = db.query(Project).filter(
        Project.id == session.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    current_ids = list(session.trace_ids or [])
    if trace_id not in current_ids:
        raise HTTPException(status_code=404, detail="Trace not found in this session")

    current_ids.remove(trace_id)
    session.trace_ids = current_ids
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_dict(session)


@router.post("/{session_id}/score", tags=["sessions"])
async def score_session(
    session_id: str,
    payload: ManualScorePayload,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Score a session.
    - scorer_type == "from_traces": aggregate existing per-trace Score records by metric name
                                    (same metrics as on individual traces). Falls back to Ollama
                                    if no trace scores exist yet.
    - scorer_type == "ollama": re-score every linked trace via Ollama LLM and average.
    - scorer_type == "human": save manual_score directly.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project = db.query(Project).filter(
        Project.id == session.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    if payload.scorer_type == "from_traces":
        # ── Aggregate existing trace Score records ──────────────────────────
        if not session.trace_ids:
            raise HTTPException(status_code=400, detail="Session has no traces to score")

        # Fetch all Score rows for the traces in this session,
        # excluding scores created by this session itself (avoid double-counting).
        rows = (
            db.query(Score)
            .filter(
                Score.trace_id.in_(session.trace_ids),
                Score.scorer_name != "session_ollama",  # skip session-level scores
            )
            .all()
        )

        if not rows:
            # No existing trace scores → fall back to Ollama
            payload.scorer_type = "ollama"
        else:
            # Group by scorer_name and compute per-metric averages
            from collections import defaultdict
            buckets: dict = defaultdict(list)
            for r in rows:
                buckets[r.scorer_name].append(r.score_value)

            agg: dict = {
                name: round(sum(vals) / len(vals), 4)
                for name, vals in buckets.items()
            }
            overall = round(sum(agg.values()) / len(agg), 4) if agg else 0.0

            session.manual_score = overall
            session.aggregate_scores = agg
            session.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
            return _session_to_dict(session)

    if payload.scorer_type == "ollama":
        if not session.trace_ids:
            raise HTTPException(status_code=400, detail="Session has no traces to score")

        from backend.scoring import OllamaScorer
        from backend.config import settings as cfg

        traces = db.query(Trace).filter(Trace.id.in_(session.trace_ids)).all()
        scorer = OllamaScorer(model=payload.model or "llama2", ollama_url=cfg.OLLAMA_API_URL)

        scores_collected = []
        for trace in traces:
            try:
                score_val, explanation = await scorer.score_async(
                    trace, scorer_name="session_ollama"
                )
                scores_collected.append(score_val)
                # Persist per-trace score
                score_row = Score(
                    id=str(uuid.uuid4()),
                    trace_id=trace.id,
                    project_id=session.project_id,
                    scorer_name="session_ollama",
                    scorer_type="llm",
                    score_value=score_val,
                    explanation=explanation,
                    model_used=payload.model or "llama2",
                    scorer_config={"session_id": session_id},
                )
                db.add(score_row)
            except Exception as exc:
                logger.warning(f"Ollama scoring failed for trace {trace.id}: {exc}")

        avg_score = sum(scores_collected) / len(scores_collected) if scores_collected else 0.0
        session.manual_score = round(avg_score, 4)
        session.aggregate_scores = {
            **(session.aggregate_scores or {}),
            "session_ollama": round(avg_score, 4),
        }
    else:
        # Human / manual score
        raw = payload.manual_score if payload.manual_score is not None else 0.0
        score = max(0.0, min(1.0, raw))
        session.manual_score = round(score, 4)
        session.aggregate_scores = {
            **(session.aggregate_scores or {}),
            "manual": round(score, 4),
        }

    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_dict(session)
