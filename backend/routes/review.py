"""
Human Review Queue — flag traces for manual review, assign reviewers, track outcomes.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import ReviewTask, Trace, User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReviewTaskCreate(BaseModel):
    project_id: str
    trace_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    priority: str = "medium"            # critical, high, medium, low
    reason: Optional[str] = None        # low_score, anomaly, manual, policy
    score_at_flagging: Optional[float] = None
    threshold_violated: Optional[str] = None


class ReviewTaskUpdate(BaseModel):
    status: Optional[str] = None        # pending, in_review, approved, rejected, escalated
    notes: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None


def _task_to_dict(t: ReviewTask) -> dict:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "trace_id": t.trace_id,
        "created_by": t.created_by,
        "assigned_to": t.assigned_to,
        "title": t.title,
        "description": t.description,
        "priority": t.priority,
        "status": t.status,
        "reason": t.reason,
        "notes": t.notes,
        "score_at_flagging": t.score_at_flagging,
        "threshold_violated": t.threshold_violated,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/tasks", status_code=201)
def create_review_task(
    payload: ReviewTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flag a trace (or create a standalone task) for human review."""
    # Verify trace exists if provided
    if payload.trace_id:
        trace = db.query(Trace).filter_by(id=payload.trace_id).first()
        if not trace:
            raise HTTPException(404, f"Trace {payload.trace_id} not found")

    task = ReviewTask(
        project_id=payload.project_id,
        trace_id=payload.trace_id,
        created_by=current_user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        reason=payload.reason or "manual",
        score_at_flagging=payload.score_at_flagging,
        threshold_violated=payload.threshold_violated,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_to_dict(task)


@router.get("/queue")
def get_review_queue(
    project_id: str,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return pending/active review tasks ordered by priority then creation time."""
    PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    q = db.query(ReviewTask).filter_by(project_id=project_id)
    if status:
        q = q.filter(ReviewTask.status == status)
    else:
        # Default: show actionable items
        q = q.filter(ReviewTask.status.in_(["pending", "in_review", "escalated"]))
    if priority:
        q = q.filter(ReviewTask.priority == priority)

    tasks = q.order_by(ReviewTask.created_at.desc()).offset(offset).limit(limit).all()

    # Sort by priority in Python (avoids CASE SQL)
    tasks.sort(key=lambda t: (PRIORITY_ORDER.get(t.priority, 99), t.created_at))

    total = db.query(ReviewTask).filter_by(project_id=project_id).count()
    pending = db.query(ReviewTask).filter_by(project_id=project_id, status="pending").count()
    in_review = db.query(ReviewTask).filter_by(project_id=project_id, status="in_review").count()

    return {
        "tasks": [_task_to_dict(t) for t in tasks],
        "total": total,
        "pending": pending,
        "in_review": in_review,
    }


@router.get("/tasks/{task_id}")
def get_review_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(ReviewTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(404, "Review task not found")

    result = _task_to_dict(task)

    # Enrich with trace data if linked
    if task.trace_id:
        trace = db.query(Trace).filter_by(id=task.trace_id).first()
        if trace:
            result["trace"] = {
                "id": trace.id,
                "input_data": trace.input_data,
                "output_data": trace.output_data,
                "scores": trace.scores,
                "model": trace.model,
                "latency_ms": trace.latency_ms,
                "environment": getattr(trace, "environment", None),
            }
    return result


@router.patch("/tasks/{task_id}")
def update_review_task(
    task_id: str,
    payload: ReviewTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update task status, notes, priority, or assignment."""
    task = db.query(ReviewTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(404, "Review task not found")

    if payload.status:
        valid = {"pending", "in_review", "approved", "rejected", "escalated"}
        if payload.status not in valid:
            raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(valid)}")
        task.status = payload.status
        # Record review timestamp when a decision is made
        if payload.status in {"approved", "rejected"}:
            task.reviewed_at = datetime.utcnow()
    if payload.notes is not None:
        task.notes = payload.notes
    if payload.priority:
        task.priority = payload.priority
    if payload.assigned_to is not None:
        task.assigned_to = payload.assigned_to or None

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return _task_to_dict(task)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_review_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(ReviewTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(404, "Review task not found")
    db.delete(task)
    db.commit()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def review_stats(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate review queue statistics."""
    all_tasks = db.query(ReviewTask).filter_by(project_id=project_id).all()

    status_counts: dict = {}
    priority_counts: dict = {}
    reason_counts: dict = {}
    total_reviewed = 0
    avg_resolution_hours = None
    resolution_times = []

    for t in all_tasks:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1
        priority_counts[t.priority] = priority_counts.get(t.priority, 0) + 1
        reason_counts[t.reason or "manual"] = reason_counts.get(t.reason or "manual", 0) + 1
        if t.reviewed_at and t.created_at:
            total_reviewed += 1
            delta = (t.reviewed_at - t.created_at).total_seconds() / 3600
            resolution_times.append(delta)

    if resolution_times:
        avg_resolution_hours = round(sum(resolution_times) / len(resolution_times), 2)

    return {
        "total": len(all_tasks),
        "by_status": status_counts,
        "by_priority": priority_counts,
        "by_reason": reason_counts,
        "total_reviewed": total_reviewed,
        "avg_resolution_hours": avg_resolution_hours,
        "backlog": status_counts.get("pending", 0) + status_counts.get("in_review", 0),
    }


# ---------------------------------------------------------------------------
# Auto-flag: scan recent traces below a score threshold
# ---------------------------------------------------------------------------

@router.post("/auto-flag")
def auto_flag_low_score_traces(
    project_id: str,
    threshold: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-create review tasks for recent traces with scores below threshold."""
    from sqlalchemy import and_

    # Find traces that already have overall_score set and are below threshold
    low_traces = (
        db.query(Trace)
        .filter(
            Trace.project_id == project_id,
            Trace.overall_score.isnot(None),
            Trace.overall_score < threshold,
        )
        .order_by(Trace.created_at.desc())
        .limit(limit)
        .all()
    )

    # Skip traces already in queue
    existing_trace_ids = {
        t.trace_id
        for t in db.query(ReviewTask.trace_id)
        .filter(ReviewTask.project_id == project_id, ReviewTask.trace_id.isnot(None))
        .all()
    }

    created = []
    for trace in low_traces:
        if trace.id in existing_trace_ids:
            continue
        score = float(trace.overall_score)
        priority = "critical" if score < 0.3 else ("high" if score < 0.4 else "medium")
        task = ReviewTask(
            project_id=project_id,
            trace_id=trace.id,
            created_by=current_user.id,
            title=f"Low score trace — {score:.0%}",
            description=f"Trace scored {score:.2f} (below threshold {threshold:.2f})",
            priority=priority,
            reason="low_score",
            score_at_flagging=score,
            threshold_violated=f"overall_score < {threshold}",
        )
        db.add(task)
        created.append(trace.id)

    db.commit()
    return {"flagged": len(created), "trace_ids": created}
