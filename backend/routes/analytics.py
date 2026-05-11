"""
Analytics routes — time-series metrics, cost breakdown, model comparisons.
"""



from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Trace, Score, Eval, GatewayRequest, User

router = APIRouter()


@router.get("/overview")
def get_overview(
    project_id: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """High-level project metrics for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    total_traces = (
        db.query(func.count(Trace.id))
        .filter(Trace.project_id == project_id, Trace.timestamp >= since)
        .scalar() or 0
    )
    error_traces = (
        db.query(func.count(Trace.id))
        .filter(Trace.project_id == project_id, Trace.timestamp >= since, Trace.status == "error")
        .scalar() or 0
    )
    avg_latency = (
        db.query(func.avg(Trace.latency_ms))
        .filter(Trace.project_id == project_id, Trace.timestamp >= since, Trace.latency_ms.isnot(None))
        .scalar()
    )
    total_cost = (
        db.query(func.sum(Trace.cost_usd))
        .filter(Trace.project_id == project_id, Trace.timestamp >= since, Trace.cost_usd.isnot(None))
        .scalar()
    )
    total_tokens = (
        db.query(func.sum(Trace.total_tokens))
        .filter(Trace.project_id == project_id, Trace.timestamp >= since, Trace.total_tokens.isnot(None))
        .scalar()
    )

    return {
        "total_traces": total_traces,
        "error_traces": error_traces,
        "error_rate": round(error_traces / max(total_traces, 1), 4),
        "avg_latency_ms": round(float(avg_latency), 2) if avg_latency else None,
        "total_cost_usd": round(float(total_cost), 6) if total_cost else 0.0,
        "total_tokens": int(total_tokens) if total_tokens else 0,
        "days": days,
    }


@router.get("/timeseries")
def get_timeseries(
    project_id: str,
    metric: str = Query("trace_count", enum=["trace_count", "error_count", "avg_latency", "total_cost", "total_tokens"]),
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Daily time-series for a chosen metric."""
    since = datetime.utcnow() - timedelta(days=days)

    # Fetch raw traces in window
    rows = (
        db.query(
            func.date(Trace.timestamp).label("day"),
            func.count(Trace.id).label("trace_count"),
            func.count(Trace.id).filter(Trace.status == "error").label("error_count"),
            func.avg(Trace.latency_ms).label("avg_latency"),
            func.sum(func.coalesce(Trace.cost_usd, 0)).label("total_cost"),
            func.sum(func.coalesce(Trace.total_tokens, 0)).label("total_tokens"),
        )
        .filter(Trace.project_id == project_id, Trace.timestamp >= since)
        .group_by(func.date(Trace.timestamp))
        .order_by(func.date(Trace.timestamp))
        .all()
    )

    series = []
    for row in rows:
        value = getattr(row, metric, 0) or 0
        series.append({"date": str(row.day), "value": round(float(value), 4)})

    return {"metric": metric, "series": series}


@router.get("/models")
def get_model_breakdown(
    project_id: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Usage & performance stats broken down by model."""
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            Trace.model,
            func.count(Trace.id).label("count"),
            func.avg(Trace.latency_ms).label("avg_latency"),
            func.avg(Trace.cost_usd).label("avg_cost"),
            func.sum(func.coalesce(Trace.total_tokens, 0)).label("total_tokens"),
            func.count(Trace.id).filter(Trace.status == "error").label("errors"),
        )
        .filter(Trace.project_id == project_id, Trace.timestamp >= since)
        .group_by(Trace.model)
        .order_by(func.count(Trace.id).desc())
        .all()
    )

    return [
        {
            "model": row.model or "unknown",
            "count": row.count,
            "avg_latency_ms": round(float(row.avg_latency), 2) if row.avg_latency else None,
            "avg_cost_usd": round(float(row.avg_cost), 6) if row.avg_cost else 0.0,
            "total_tokens": int(row.total_tokens),
            "error_rate": round(row.errors / max(row.count, 1), 4),
        }
        for row in rows
    ]


@router.get("/scores")
def get_score_trends(
    project_id: str,
    scorer_name: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Average scores over time, optionally filtered to one scorer."""
    since = datetime.utcnow() - timedelta(days=days)

    q = db.query(
        func.date(Score.created_at).label("day"),
        Score.scorer_name,
        func.avg(Score.score_value).label("avg_score"),
        func.count(Score.id).label("count"),
    ).filter(
        Score.project_id == project_id,
        Score.created_at >= since,
    )
    if scorer_name:
        q = q.filter(Score.scorer_name == scorer_name)

    rows = q.group_by(func.date(Score.created_at), Score.scorer_name).order_by(func.date(Score.created_at)).all()

    return [
        {
            "date": str(row.day),
            "scorer_name": row.scorer_name,
            "avg_score": round(float(row.avg_score), 4),
            "count": row.count,
        }
        for row in rows
    ]
