"""
Topics routes — ML-powered pattern discovery in trace logs.
"""



from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from backend.topics import topics_engine
from database.models import Topic, TopicAssignment, Trace, User

router = APIRouter()


@router.get("/summary")
def get_topics_summary(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All topics grouped by facet type for a project."""
    return topics_engine.get_topics_summary(db, project_id)


@router.get("/{topic_id}/traces")
def get_topic_traces(
    topic_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List traces assigned to a specific topic."""
    topic = db.query(Topic).filter_by(id=topic_id).first()
    if not topic:
        raise HTTPException(404, "Topic not found")

    assignments = (
        db.query(TopicAssignment)
        .filter_by(topic_id=topic_id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    trace_ids = [a.trace_id for a in assignments]
    traces = db.query(Trace).filter(Trace.id.in_(trace_ids)).all()

    return {
        "topic": {"id": topic.id, "name": topic.name, "facet_type": topic.facet_type},
        "traces": [
            {
                "id": t.id,
                "model": t.model,
                "status": t.status,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "latency_ms": t.latency_ms,
            }
            for t in traces
        ],
        "total": topic.trace_count,
    }


@router.post("/analyse/{trace_id}")
def analyse_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run topic analysis on a single trace and persist results."""
    trace = db.query(Trace).filter_by(id=trace_id).first()
    if not trace:
        raise HTTPException(404, "Trace not found")

    topics_engine.assign_topics_to_trace(db, trace)
    db.commit()
    return {"message": "Topics assigned", "trace_id": trace_id}


@router.post("/reanalyse")
def reanalyse_project(
    project_id: str,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run topic analysis across the most recent traces in a project."""
    traces = (
        db.query(Trace)
        .filter_by(project_id=project_id)
        .order_by(Trace.timestamp.desc())
        .limit(limit)
        .all()
    )
    for trace in traces:
        topics_engine.assign_topics_to_trace(db, trace)
    db.commit()
    return {"analysed": len(traces), "project_id": project_id}
