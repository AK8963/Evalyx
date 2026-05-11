"""
Custom dashboards & alerts routes.
"""



from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Alert, CustomDashboard, User

router = APIRouter()


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

class DashboardCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    widgets: List[Dict] = []
    is_public: bool = False


@router.post("/", status_code=201)
def create_dashboard(
    payload: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = CustomDashboard(
        project_id=payload.project_id,
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
        widgets=payload.widgets,
        is_public=payload.is_public,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return _dash_dict(d)


@router.get("/")
def list_dashboards(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashes = db.query(CustomDashboard).filter_by(project_id=project_id).order_by(CustomDashboard.created_at.desc()).all()
    return [_dash_dict(d) for d in dashes]


@router.get("/{dashboard_id}")
def get_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = db.query(CustomDashboard).filter_by(id=dashboard_id).first()
    if not d:
        raise HTTPException(404, "Dashboard not found")
    return _dash_dict(d)


@router.put("/{dashboard_id}")
def update_dashboard(
    dashboard_id: str,
    payload: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = db.query(CustomDashboard).filter_by(id=dashboard_id, owner_id=current_user.id).first()
    if not d:
        raise HTTPException(404, "Dashboard not found")
    d.name = payload.name
    d.description = payload.description
    d.widgets = payload.widgets
    d.is_public = payload.is_public
    db.commit()
    return _dash_dict(d)


@router.delete("/{dashboard_id}")
def delete_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = db.query(CustomDashboard).filter_by(id=dashboard_id, owner_id=current_user.id).first()
    if not d:
        raise HTTPException(404, "Dashboard not found")
    db.delete(d)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertCreate(BaseModel):
    project_id: str
    name: str
    metric: str
    condition: str     # 'lt', 'gt', 'eq'
    threshold: float
    window_minutes: int = 60
    webhook_url: Optional[str] = None


@router.post("/alerts", status_code=201)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    alerts = db.query(Alert).filter_by(project_id=project_id).all()
    return [_alert_dict(a) for a in alerts]


@router.delete("/alerts/{alert_id}")
def delete_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Alert).filter_by(id=alert_id).first()
    if not a:
        raise HTTPException(404, "Alert not found")
    db.delete(a)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dash_dict(d: CustomDashboard) -> Dict:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "name": d.name,
        "description": d.description,
        "widgets": d.widgets,
        "is_public": d.is_public,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _alert_dict(a: Alert) -> Dict:
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
    }
