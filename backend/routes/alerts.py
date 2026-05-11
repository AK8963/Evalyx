"""
Alert Channels & Rules — Phase 3 Enterprise implementation.

Manages delivery channels (Slack, Email, Webhook) and alert rules
that fire when metrics cross thresholds.

Endpoints:
  GET/POST   /api/alerts/channels              — list / create channels
  GET/PATCH/DELETE /api/alerts/channels/{id}   — manage a channel
  POST       /api/alerts/channels/{id}/test    — send a test message
  GET/POST   /api/alerts/rules                 — list / create rules
  GET/PATCH/DELETE /api/alerts/rules/{id}      — manage a rule
  POST       /api/alerts/evaluate              — manually evaluate rules now
"""

import hashlib
import hmac
import json
import logging
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Alert, AlertChannel, AlertRule, EmailConfig, Trace, Score, User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChannelCreate(BaseModel):
    project_id: str
    name: str
    channel_type: str           # "slack" | "email" | "webhook"
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    email_recipients: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    email_recipients: Optional[str] = None
    webhook_url: Optional[str] = None
    is_active: Optional[bool] = None


class RuleCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    metric: str              # error_rate | avg_score | latency_p99 | cost_usd | trace_count
    condition: str           # gt | lt | gte | lte | eq
    threshold: float
    window_minutes: int = 60
    channel_ids: List[str] = []
    cooldown_minutes: int = 30


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    metric: Optional[str] = None
    condition: Optional[str] = None
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    channel_ids: Optional[List[str]] = None
    cooldown_minutes: Optional[int] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Delivery helpers
# ---------------------------------------------------------------------------

def _send_slack(webhook_url: str, message: str, attachments: List[Dict] = None) -> bool:
    """Send a Slack message via incoming webhook."""
    payload: Dict[str, Any] = {"text": message}
    if attachments:
        payload["attachments"] = attachments
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Slack send failed: {e}")
        return False


def _send_email_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_username: Optional[str],
    smtp_password: Optional[str],
    use_tls: bool,
    from_addr: str,
    from_name: str,
    recipients: List[str],
    subject: str,
    body_html: str,
) -> bool:
    """Send email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body_html, "html"))

    try:
        context = ssl.create_default_context()
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.starttls(context=context)
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.sendmail(from_addr, recipients, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.sendmail(from_addr, recipients, msg.as_string())
        return True
    except Exception as e:
        logger.warning(f"Email send failed: {e}")
        return False


def _send_webhook(url: str, secret: Optional[str], payload: Dict) -> bool:
    """Send signed generic webhook."""
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-TraceIQ-Signature"] = f"sha256={sig}"
    try:
        resp = httpx.post(url, content=body, headers=headers, timeout=10)
        return resp.status_code < 400
    except Exception as e:
        logger.warning(f"Webhook send failed: {e}")
        return False


def _build_alert_message(rule: AlertRule, value: float) -> str:
    cond_label = {"gt": ">", "lt": "<", "gte": "≥", "lte": "≤", "eq": "="}.get(rule.condition, rule.condition)
    return (
        f"🚨 *TraceIQ Alert*: `{rule.name}`\n"
        f"Metric `{rule.metric}` is `{value:.4f}` (threshold: {cond_label} `{rule.threshold}`)\n"
        f"Window: last {rule.window_minutes} minutes"
    )


def _alert_email_html(rule: AlertRule, value: float) -> str:
    cond_label = {"gt": ">", "lt": "<", "gte": "≥", "lte": "≤", "eq": "="}.get(rule.condition, rule.condition)
    return f"""
<html><body style="font-family:sans-serif;max-width:600px;">
  <h2 style="color:#dc2626;">🚨 TraceIQ Alert Fired</h2>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:8px;font-weight:bold;">Rule</td><td style="padding:8px;">{rule.name}</td></tr>
    <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;">Metric</td><td style="padding:8px;">{rule.metric}</td></tr>
    <tr><td style="padding:8px;font-weight:bold;">Value</td><td style="padding:8px;">{value:.4f}</td></tr>
    <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;">Condition</td><td style="padding:8px;">{cond_label} {rule.threshold}</td></tr>
    <tr><td style="padding:8px;font-weight:bold;">Window</td><td style="padding:8px;">Last {rule.window_minutes} minutes</td></tr>
  </table>
  <p style="color:#6b7280;font-size:12px;margin-top:16px;">This alert was sent by TraceIQ. Manage alerts at your TraceIQ dashboard.</p>
</body></html>"""


def _deliver_to_channel(channel: AlertChannel, rule: AlertRule, value: float, db: Session):
    """Deliver an alert notification to one channel."""
    ok = False
    error = None
    msg = _build_alert_message(rule, value)

    try:
        if channel.channel_type == "slack":
            ok = _send_slack(
                channel.slack_webhook_url,
                msg,
                attachments=[{
                    "color": "danger",
                    "fields": [
                        {"title": "Metric", "value": rule.metric, "short": True},
                        {"title": "Value", "value": f"{value:.4f}", "short": True},
                        {"title": "Threshold", "value": str(rule.threshold), "short": True},
                        {"title": "Window", "value": f"{rule.window_minutes} min", "short": True},
                    ],
                }],
            )
        elif channel.channel_type == "email":
            recipients = [r.strip() for r in (channel.email_recipients or "").split(",") if r.strip()]
            if not recipients:
                return
            # Try org EmailConfig first, fall back to app SMTP
            smtp = _get_smtp_config(channel.project_id, db)
            if smtp:
                ok = _send_email_smtp(
                    smtp["host"], smtp["port"], smtp["username"], smtp["password"],
                    smtp["use_tls"], smtp["from_address"], smtp["from_name"],
                    recipients,
                    f"[TraceIQ Alert] {rule.name}",
                    _alert_email_html(rule, value),
                )
            else:
                logger.warning("No SMTP config available for alert email delivery")
        elif channel.channel_type == "webhook":
            ok = _send_webhook(
                channel.webhook_url,
                channel.webhook_secret,
                {
                    "event": "alert.fired",
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "metric": rule.metric,
                    "value": value,
                    "threshold": rule.threshold,
                    "condition": rule.condition,
                    "fired_at": datetime.utcnow().isoformat(),
                },
            )
    except Exception as e:
        ok = False
        error = str(e)

    channel.last_used_at = datetime.utcnow()
    channel.last_error = None if ok else (error or "Delivery failed")
    db.commit()


def _get_smtp_config(project_id: str, db: Session) -> Optional[Dict]:
    """Resolve SMTP config: try org EmailConfig first, then app settings."""
    from database.models import Project, Organization
    project = db.query(Project).filter_by(id=project_id).first()
    if project:
        from database.models import OrganizationMember
        org_member = db.query(OrganizationMember).filter_by(project_id=project_id).first() if hasattr(OrganizationMember, 'project_id') else None
        # Try to find org via project owner
        email_cfg = db.query(EmailConfig).first()  # Simplified: use first active config
        if email_cfg and email_cfg.is_active:
            return {
                "host": email_cfg.smtp_host,
                "port": email_cfg.smtp_port,
                "username": email_cfg.smtp_username,
                "password": email_cfg.smtp_password,
                "use_tls": email_cfg.smtp_use_tls,
                "from_address": email_cfg.from_address,
                "from_name": email_cfg.from_name,
            }
    # Fall back to app config
    if settings.SMTP_HOST:
        return {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "username": settings.SMTP_USERNAME,
            "password": settings.SMTP_PASSWORD,
            "use_tls": settings.SMTP_USE_TLS,
            "from_address": settings.SMTP_FROM_ADDRESS,
            "from_name": settings.SMTP_FROM_NAME,
        }
    return None


# ---------------------------------------------------------------------------
# Metric evaluation
# ---------------------------------------------------------------------------

def _evaluate_metric(rule: AlertRule, db: Session) -> Optional[float]:
    """Compute the current value of the rule's metric over the time window."""
    since = datetime.utcnow() - timedelta(minutes=rule.window_minutes)
    q = db.query(Trace).filter(
        Trace.project_id == rule.project_id,
        Trace.timestamp >= since,
    )
    total = q.count()
    if total == 0:
        return None

    if rule.metric == "error_rate":
        errors = q.filter(Trace.status == "error").count()
        return errors / total

    if rule.metric == "trace_count":
        return float(total)

    if rule.metric == "avg_score":
        result = db.query(func.avg(Score.score_value)).filter(
            Score.project_id == rule.project_id,
            Score.created_at >= since,
        ).scalar()
        return float(result) if result is not None else None

    if rule.metric == "latency_p99":
        latencies = [
            r.latency_ms for r in q.all()
            if r.latency_ms is not None
        ]
        if not latencies:
            return None
        latencies.sort()
        p99_idx = int(len(latencies) * 0.99)
        return latencies[min(p99_idx, len(latencies) - 1)]

    if rule.metric == "cost_usd":
        result = db.query(func.sum(Trace.cost_usd)).filter(
            Trace.project_id == rule.project_id,
            Trace.timestamp >= since,
        ).scalar()
        return float(result) if result is not None else None

    return None


def _condition_met(condition: str, value: float, threshold: float) -> bool:
    ops = {"gt": value > threshold, "lt": value < threshold,
           "gte": value >= threshold, "lte": value <= threshold, "eq": abs(value - threshold) < 1e-9}
    return ops.get(condition, False)


def _evaluate_and_fire(rule_id: str, db_url: str):
    """Background task: evaluate one rule and fire if needed."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        rule = db.query(AlertRule).filter_by(id=rule_id, is_active=True).first()
        if not rule:
            return

        # Cooldown check
        if rule.last_fired_at:
            cooldown_end = rule.last_fired_at + timedelta(minutes=rule.cooldown_minutes)
            if datetime.utcnow() < cooldown_end:
                return

        value = _evaluate_metric(rule, db)
        if value is None:
            return

        rule.last_value = value
        db.commit()

        if not _condition_met(rule.condition, value, rule.threshold):
            return

        # Fire! Deliver to all channels
        rule.last_fired_at = datetime.utcnow()
        db.commit()

        for channel_id in (rule.channel_ids or []):
            channel = db.query(AlertChannel).filter_by(id=channel_id, is_active=True).first()
            if channel:
                _deliver_to_channel(channel, rule, value, db)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Channel endpoints
# ---------------------------------------------------------------------------

@router.get("/channels")
def list_channels(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    channels = db.query(AlertChannel).filter_by(project_id=project_id).all()
    return [_channel_dict(c) for c in channels]


@router.post("/channels", status_code=201)
def create_channel(
    payload: ChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.channel_type == "slack" and not payload.slack_webhook_url:
        raise HTTPException(400, "slack_webhook_url is required for Slack channels")
    if payload.channel_type == "email" and not payload.email_recipients:
        raise HTTPException(400, "email_recipients is required for email channels")
    if payload.channel_type == "webhook" and not payload.webhook_url:
        raise HTTPException(400, "webhook_url is required for webhook channels")

    ch = AlertChannel(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        channel_type=payload.channel_type,
        slack_webhook_url=payload.slack_webhook_url,
        slack_channel=payload.slack_channel,
        email_recipients=payload.email_recipients,
        webhook_url=payload.webhook_url,
        webhook_secret=payload.webhook_secret,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return _channel_dict(ch)


@router.get("/channels/{channel_id}")
def get_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ch = db.query(AlertChannel).filter_by(id=channel_id).first()
    if not ch:
        raise HTTPException(404, "Channel not found")
    return _channel_dict(ch)


@router.patch("/channels/{channel_id}")
def update_channel(
    channel_id: str,
    payload: ChannelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ch = db.query(AlertChannel).filter_by(id=channel_id).first()
    if not ch:
        raise HTTPException(404, "Channel not found")
    for k, v in payload.dict(exclude_none=True).items():
        setattr(ch, k, v)
    db.commit()
    return _channel_dict(ch)


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ch = db.query(AlertChannel).filter_by(id=channel_id).first()
    if not ch:
        raise HTTPException(404, "Channel not found")
    db.delete(ch)
    db.commit()


@router.post("/channels/{channel_id}/test")
def test_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a test message to a channel."""
    ch = db.query(AlertChannel).filter_by(id=channel_id).first()
    if not ch:
        raise HTTPException(404, "Channel not found")

    ok = False
    error = None
    test_msg = "✅ TraceIQ test notification — your alert channel is working!"

    if ch.channel_type == "slack":
        ok = _send_slack(ch.slack_webhook_url, test_msg)
        if not ok:
            error = "Slack webhook returned non-200 response"

    elif ch.channel_type == "email":
        recipients = [r.strip() for r in (ch.email_recipients or "").split(",") if r.strip()]
        smtp = _get_smtp_config(ch.project_id, db)
        if not smtp:
            return {"ok": False, "error": "No SMTP configuration found. Configure SMTP in the Email Settings page."}
        ok = _send_email_smtp(
            smtp["host"], smtp["port"], smtp["username"], smtp["password"],
            smtp["use_tls"], smtp["from_address"], smtp["from_name"],
            recipients,
            "[TraceIQ] Test Alert Notification",
            f"<html><body><p>{test_msg}</p></body></html>",
        )
        if not ok:
            error = "SMTP send failed"

    elif ch.channel_type == "webhook":
        ok = _send_webhook(ch.webhook_url, ch.webhook_secret, {
            "event": "test", "message": test_msg, "timestamp": datetime.utcnow().isoformat()
        })
        if not ok:
            error = "Webhook returned error response"

    ch.last_used_at = datetime.utcnow()
    ch.last_error = None if ok else error
    db.commit()
    return {"ok": ok, "error": error}


# ---------------------------------------------------------------------------
# Rule endpoints
# ---------------------------------------------------------------------------

@router.get("/rules")
def list_rules(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rules = db.query(AlertRule).filter_by(project_id=project_id).all()
    return [_rule_dict(r) for r in rules]


@router.post("/rules", status_code=201)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = AlertRule(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        metric=payload.metric,
        condition=payload.condition,
        threshold=payload.threshold,
        window_minutes=payload.window_minutes,
        channel_ids=payload.channel_ids,
        cooldown_minutes=payload.cooldown_minutes,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_dict(rule)


@router.get("/rules/{rule_id}")
def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Alert rule not found")
    return _rule_dict(rule)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Alert rule not found")
    for k, v in payload.dict(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    return _rule_dict(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Alert rule not found")
    db.delete(rule)
    db.commit()


@router.post("/rules/{rule_id}/evaluate")
def evaluate_rule_now(
    rule_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger evaluation of one alert rule."""
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Alert rule not found")
    background_tasks.add_task(_evaluate_and_fire, rule_id, settings.DATABASE_URL)
    return {"message": "Evaluation queued", "rule_id": rule_id}


@router.post("/evaluate")
def evaluate_all_rules(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate all active rules for a project."""
    rules = db.query(AlertRule).filter_by(project_id=project_id, is_active=True).all()
    for rule in rules:
        background_tasks.add_task(_evaluate_and_fire, rule.id, settings.DATABASE_URL)
    return {"message": f"Queued {len(rules)} rules for evaluation"}


# ---------------------------------------------------------------------------
# Email config endpoints
# ---------------------------------------------------------------------------

class EmailConfigCreate(BaseModel):
    organization_id: str
    smtp_host: str
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    from_address: str
    from_name: str = "TraceIQ Alerts"


@router.get("/email-config/{org_id}")
def get_email_config(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = db.query(EmailConfig).filter_by(organization_id=org_id).first()
    if not cfg:
        raise HTTPException(404, "No email config found")
    return _email_config_dict(cfg)


@router.post("/email-config", status_code=201)
def upsert_email_config(
    payload: EmailConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = db.query(EmailConfig).filter_by(organization_id=payload.organization_id).first()
    if cfg is None:
        cfg = EmailConfig(organization_id=payload.organization_id, created_by=current_user.id)
        db.add(cfg)
    for k, v in payload.dict(exclude={"organization_id"}).items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return _email_config_dict(cfg)


@router.post("/email-config/{org_id}/test")
def test_email_config(
    org_id: str,
    test_recipient: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = db.query(EmailConfig).filter_by(organization_id=org_id).first()
    if not cfg:
        raise HTTPException(404, "No email config found")
    ok = _send_email_smtp(
        cfg.smtp_host, cfg.smtp_port, cfg.smtp_username, cfg.smtp_password,
        cfg.smtp_use_tls, cfg.from_address, cfg.from_name,
        [test_recipient],
        "[TraceIQ] SMTP Test",
        "<html><body><p>✅ Your TraceIQ SMTP configuration is working correctly.</p></body></html>",
    )
    cfg.last_tested_at = datetime.utcnow()
    cfg.last_test_result = "ok" if ok else "error"
    cfg.last_test_error = None if ok else "SMTP delivery failed"
    db.commit()
    return {"ok": ok, "error": cfg.last_test_error}


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _channel_dict(ch: AlertChannel) -> dict:
    return {
        "id": ch.id,
        "project_id": ch.project_id,
        "name": ch.name,
        "channel_type": ch.channel_type,
        "slack_channel": ch.slack_channel,
        "email_recipients": ch.email_recipients,
        "slack_webhook_url": "***" if ch.slack_webhook_url else None,
        "webhook_url": ch.webhook_url,
        "is_active": ch.is_active,
        "last_used_at": ch.last_used_at.isoformat() if ch.last_used_at else None,
        "last_error": ch.last_error,
        "created_at": ch.created_at.isoformat() if ch.created_at else None,
    }


def _rule_dict(r: AlertRule) -> dict:
    return {
        "id": r.id,
        "project_id": r.project_id,
        "name": r.name,
        "description": r.description,
        "metric": r.metric,
        "condition": r.condition,
        "threshold": r.threshold,
        "window_minutes": r.window_minutes,
        "channel_ids": r.channel_ids,
        "cooldown_minutes": r.cooldown_minutes,
        "is_active": r.is_active,
        "last_value": r.last_value,
        "last_fired_at": r.last_fired_at.isoformat() if r.last_fired_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _email_config_dict(cfg: EmailConfig) -> dict:
    return {
        "id": cfg.id,
        "organization_id": cfg.organization_id,
        "smtp_host": cfg.smtp_host,
        "smtp_port": cfg.smtp_port,
        "smtp_username": cfg.smtp_username,
        "smtp_password": "***" if cfg.smtp_password else None,
        "smtp_use_tls": cfg.smtp_use_tls,
        "from_address": cfg.from_address,
        "from_name": cfg.from_name,
        "is_active": cfg.is_active,
        "last_tested_at": cfg.last_tested_at.isoformat() if cfg.last_tested_at else None,
        "last_test_result": cfg.last_test_result,
    }
