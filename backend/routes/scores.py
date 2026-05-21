"""
Scores routes - project-wide view of all evaluation scores.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc
from typing import Optional, Any
from pydantic import BaseModel
from database.models import Score, Trace, Project
from backend.database import get_db
from backend.routes.auth import get_current_user
from datetime import datetime, timedelta


class ScoreCreate(BaseModel):
    trace_id: str
    project_id: str
    scorer_name: str
    scorer_type: str  # llm, code, human, expected, semantic
    score_value: float
    explanation: Optional[str] = None
    scorer_config: Optional[Any] = None
    model_used: Optional[str] = None

router = APIRouter()


def _score_to_dict(score: Score) -> dict:
    trace = score.trace
    return {
        "id": score.id,
        "trace_id": score.trace_id,
        "project_id": score.project_id,
        "scorer_name": score.scorer_name,
        "scorer_type": score.scorer_type,
        "score_value": score.score_value,
        "explanation": score.explanation,
        "scorer_config": score.scorer_config,
        "model_used": score.model_used,
        "created_at": score.created_at.isoformat() if score.created_at else None,
        "updated_at": score.updated_at.isoformat() if score.updated_at else None,
        # Trace context
        "trace": {
            "model": trace.model if trace else None,
            "status": trace.status if trace else None,
            "latency_ms": trace.latency_ms if trace else None,
            "total_tokens": trace.total_tokens if trace else None,
            "cost_usd": float(trace.cost_usd) if trace and trace.cost_usd is not None else None,
            "timestamp": trace.timestamp.isoformat() if trace and trace.timestamp else None,
            "input_data": trace.input_data if trace else None,
            "output_data": trace.output_data if trace else None,
        } if trace else None,
    }


@router.get("", tags=["scores"])
async def list_scores(
    project_id: str = Query(...),
    scorer_type: Optional[str] = Query(None),
    scorer_name: Optional[str] = Query(None),
    days: Optional[int] = Query(None, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List all scores for a project with optional filtering."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = (
        db.query(Score)
        .join(Trace, Score.trace_id == Trace.id)
        .filter(Score.project_id == project_id)
    )

    if scorer_type:
        query = query.filter(Score.scorer_type == scorer_type)
    if scorer_name:
        query = query.filter(Score.scorer_name.ilike(f"%{scorer_name}%"))
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Score.created_at >= cutoff)

    total = query.count()
    scores = query.order_by(desc(Score.created_at)).offset(offset).limit(limit).all()

    return {
        "items": [_score_to_dict(s) for s in scores],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{score_id}", tags=["scores"])
async def get_score(
    score_id: str,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Get a single score with full trace context."""
    score = db.query(Score).filter(Score.id == score_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")

    project = db.query(Project).filter(
        Project.id == score.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    return _score_to_dict(score)


@router.post("", tags=["scores"])
async def create_score(
    payload: ScoreCreate,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Create a manual score for a trace."""
    # Verify trace exists and belongs to a project the user can access
    trace = db.query(Trace).filter(Trace.id == payload.trace_id).first()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    project = db.query(Project).filter(
        Project.id == payload.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    score = Score(
        trace_id=payload.trace_id,
        project_id=payload.project_id,
        scorer_name=payload.scorer_name,
        scorer_type=payload.scorer_type,
        score_value=max(0.0, min(1.0, payload.score_value)),
        explanation=payload.explanation,
        scorer_config=payload.scorer_config,
        model_used=payload.model_used,
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return _score_to_dict(score)
