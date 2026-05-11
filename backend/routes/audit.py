"""
Audit logging routes — append-only compliance trail.

Phase 1 enhanced implementation:
  - Full filtering (action, user_id, resource_type, resource_id, date range)
  - Paginated list with total count
  - CSV/JSON export endpoint
  - Stats summary (most active users, top actions)
  - log_action() helper used by all other routes
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import AuditLog, User

router = APIRouter()


# ---------------------------------------------------------------------------
# List & Filter
# ---------------------------------------------------------------------------

@router.get("/")
def list_audit_logs(
    organization_id: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=365),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List audit logs with filtering. Returns logs + total count."""
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(AuditLog).filter(AuditLog.created_at >= since)

    if organization_id:
        q = q.filter(AuditLog.organization_id == organization_id)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        q = q.filter(AuditLog.resource_id == resource_id)

    total = q.count()
    logs = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    # Enrich with user emails
    user_ids = list({l.user_id for l in logs if l.user_id})
    users_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.email for u in users}

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": [_log_dict(l, users_map) for l in logs],
    }


@router.get("/stats")
def audit_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return summary stats: top actions, most active users, events per day."""
    since = datetime.utcnow() - timedelta(days=days)

    # Top actions
    top_actions = (
        db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= since)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    # Top users
    top_users = (
        db.query(AuditLog.user_id, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= since, AuditLog.user_id.isnot(None))
        .group_by(AuditLog.user_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    # Total events
    total = db.query(func.count(AuditLog.id)).filter(AuditLog.created_at >= since).scalar()

    # Enrich top_users with emails
    user_ids = [u.user_id for u in top_users]
    users_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.email for u in users}

    return {
        "total_events": total,
        "days": days,
        "top_actions": [{"action": a, "count": c} for a, c in top_actions],
        "top_users": [
            {"user_id": u, "email": users_map.get(u), "count": c}
            for u, c in top_users
        ],
    }


@router.get("/export")
def export_audit_logs(
    format: str = Query("csv", regex="^(csv|json)$"),
    days: int = Query(30, ge=1, le=365),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export audit logs as CSV or JSON (max 10,000 rows)."""
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(AuditLog).filter(AuditLog.created_at >= since)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)

    logs = q.order_by(AuditLog.created_at.desc()).limit(10000).all()

    if format == "json":
        import json
        data = json.dumps([_log_dict(l, {}) for l in logs], indent=2)
        return Response(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
        )

    # CSV export
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "user_id", "action", "resource_type", "resource_id",
        "ip_address", "created_at"
    ])
    writer.writeheader()
    for l in logs:
        writer.writerow({
            "id": l.id,
            "user_id": l.user_id or "",
            "action": l.action,
            "resource_type": l.resource_type or "",
            "resource_id": l.resource_id or "",
            "ip_address": l.ip_address or "",
            "created_at": l.created_at.isoformat() if l.created_at else "",
        })
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log_dict(l: AuditLog, users_map: dict) -> dict:
    return {
        "id": l.id,
        "user_id": l.user_id,
        "user_email": users_map.get(l.user_id) if l.user_id else None,
        "action": l.action,
        "resource_type": l.resource_type,
        "resource_id": l.resource_id,
        "metadata": l.extra_metadata,
        "ip_address": l.ip_address,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


# ---------------------------------------------------------------------------
# Helper used by other routes to write audit records
# ---------------------------------------------------------------------------

def log_action(
    db: Session,
    user_id: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    ip_address: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> None:
    """Write an audit log entry (fire-and-forget, does not raise)."""
    try:
        db.add(AuditLog(
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            extra_metadata=metadata,
            ip_address=ip_address,
        ))
        db.flush()
    except Exception:
        pass  # Audit logging must never break the main request
