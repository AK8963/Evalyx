"""
Webhooks & Alerts routes.
Mirrors TraceIQ: https://www.traciq.dev/docs/admin/automations/alerts
"""

import hashlib
import hmac
import json
import logging
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Alert, User, WebhookConfig

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WebhookCreate(BaseModel):
    project_id: str
    name: str
    url: str
    secret: Optional[str] = None
    events: List[str] = ["trace.created", "eval.completed", "alert.fired"]


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AlertCreate(BaseModel):
    project_id: str
    name: str
    metric: str          # 'avg_score', 'error_rate', 'latency_p99', 'cost_usd'
    condition: str       # 'lt', 'gt', 'eq'
    threshold: float
    window_minutes: int = 60
    webhook_url: Optional[str] = None


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    metric: Optional[str] = None
    condition: Optional[str] = None
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    webhook_url: Optional[str] = None
    is_active: Optional[bool] = None


def _webhook_dict(w: WebhookConfig) -> dict:
    return {
        "id": w.id,
        "project_id": w.project_id,
        "name": w.name,
        "url": w.url,
        "has_secret": bool(w.secret),
        "events": w.events or [],
        "is_active": w.is_active,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


def _alert_dict(a: Alert) -> dict:
    return {
        "id": a.id,
        "project_id": a.project_id,
        "name": a.name,
        "metric": a.metric,
        "condition": a.condition,
        "threshold": a.threshold,
        "window_minutes": a.window_minutes,
        "webhook_url": a.webhook_url,
        "is_active": a.is_active,
        "last_fired_at": a.last_fired_at.isoformat() if a.last_fired_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@router.post("/webhooks", status_code=201)
def create_webhook(
    payload: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register an outbound webhook for project events."""
    wh = WebhookConfig(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        url=payload.url,
        secret=payload.secret,
        events=payload.events,
    )
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return _webhook_dict(wh)


@router.get("/webhooks")
def list_webhooks(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    whs = db.query(WebhookConfig).filter_by(project_id=project_id).order_by(WebhookConfig.created_at.desc()).all()
    return [_webhook_dict(w) for w in whs]


@router.patch("/webhooks/{webhook_id}")
def update_webhook(
    webhook_id: str,
    payload: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wh = db.query(WebhookConfig).filter_by(id=webhook_id).first()
    if not wh:
        raise HTTPException(404, detail="Webhook not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(wh, field, value)
    db.commit()
    db.refresh(wh)
    return _webhook_dict(wh)


@router.delete("/webhooks/{webhook_id}", status_code=204)
def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wh = db.query(WebhookConfig).filter_by(id=webhook_id).first()
    if not wh:
        raise HTTPException(404, detail="Webhook not found")
    db.delete(wh)
    db.commit()


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a test ping to a registered webhook URL."""
    wh = db.query(WebhookConfig).filter_by(id=webhook_id).first()
    if not wh:
        raise HTTPException(404, detail="Webhook not found")
    payload = {"event": "test.ping", "webhook_id": webhook_id, "message": "Test ping from TraceIQ"}
    status_code = await _dispatch_webhook(wh.url, payload, secret=wh.secret)
    return {"status_code": status_code, "success": 200 <= status_code < 300}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.post("/alerts", status_code=201)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an alert rule that fires when a metric crosses a threshold."""
    valid_metrics = {"avg_score", "error_rate", "latency_p99", "latency_avg", "cost_usd", "trace_count"}
    if payload.metric not in valid_metrics:
        raise HTTPException(400, detail=f"metric must be one of: {', '.join(valid_metrics)}")
    if payload.condition not in ("lt", "gt", "eq"):
        raise HTTPException(400, detail="condition must be 'lt', 'gt', or 'eq'")

    alert = Alert(
        project_id=payload.project_id,
        owner_id=current_user.id,
        name=payload.name,
        metric=payload.metric,
        condition=payload.condition,
        threshold=payload.threshold,
        window_minutes=payload.window_minutes,
        webhook_url=payload.webhook_url,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_dict(alert)


@router.get("/alerts")
def list_alerts(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alerts = db.query(Alert).filter_by(project_id=project_id).order_by(Alert.created_at.desc()).all()
    return [_alert_dict(a) for a in alerts]


@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: str,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter_by(id=alert_id).first()
    if not alert:
        raise HTTPException(404, detail="Alert not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    db.commit()
    db.refresh(alert)
    return _alert_dict(alert)


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter_by(id=alert_id).first()
    if not alert:
        raise HTTPException(404, detail="Alert not found")
    db.delete(alert)
    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _dispatch_webhook(url: str, payload: dict, secret: Optional[str] = None) -> int:
    """Fire an outbound webhook POST. Returns HTTP status code."""
    body = json.dumps(payload, default=str)
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-TraceIQ-Signature"] = sig
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, content=body, headers=headers)
            return resp.status_code
    except Exception as e:
        logger.warning(f"Webhook dispatch failed to {url}: {e}")
        return 500


async def fire_event(project_id: str, event: str, data: dict, db: Session):
    """
    Called by other routes to fire webhook events.
    Example: await fire_event(project_id, "eval.completed", {"eval_id": ...}, db)
    """
    webhooks = db.query(WebhookConfig).filter_by(project_id=project_id, is_active=True).all()
    for wh in webhooks:
        subscribed_events = wh.events or []
        if event in subscribed_events or "*" in subscribed_events:
            payload = {"event": event, "project_id": project_id, **data}
            await _dispatch_webhook(wh.url, payload, secret=wh.secret)
