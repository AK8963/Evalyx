"""
Environments routes — manage dev / staging / production environments.
Mirrors TraceIQ: https://www.traciq.dev/docs/deploy/environments
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Environment, User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EnvironmentCreate(BaseModel):
    project_id: str
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    is_production: bool = False
    config: Dict = {}


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_production: Optional[bool] = None
    config: Optional[Dict] = None
    is_active: Optional[bool] = None


def _env_dict(e: Environment) -> dict:
    return {
        "id": e.id,
        "project_id": e.project_id,
        "name": e.name,
        "slug": e.slug,
        "description": e.description,
        "is_production": e.is_production,
        "is_active": e.is_active,
        "config": e.config or {},
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/", status_code=201)
def create_environment(
    payload: EnvironmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new environment (e.g. production, staging, dev)."""
    slug = (payload.slug or payload.name).lower().replace(" ", "-")
    existing = db.query(Environment).filter_by(
        project_id=payload.project_id, slug=slug
    ).first()
    if existing:
        raise HTTPException(400, detail=f"Environment with slug '{slug}' already exists")

    env = Environment(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        is_production=payload.is_production,
        config=payload.config,
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return _env_dict(env)


@router.get("/")
def list_environments(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all environments for a project."""
    envs = (
        db.query(Environment)
        .filter_by(project_id=project_id)
        .order_by(Environment.created_at)
        .all()
    )
    return [_env_dict(e) for e in envs]


@router.get("/{env_id}")
def get_environment(
    env_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    env = db.query(Environment).filter_by(id=env_id).first()
    if not env:
        raise HTTPException(404, detail="Environment not found")
    return _env_dict(env)


@router.patch("/{env_id}")
def update_environment(
    env_id: str,
    payload: EnvironmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    env = db.query(Environment).filter_by(id=env_id).first()
    if not env:
        raise HTTPException(404, detail="Environment not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(env, field, value)
    db.commit()
    db.refresh(env)
    return _env_dict(env)


@router.delete("/{env_id}", status_code=204)
def delete_environment(
    env_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    env = db.query(Environment).filter_by(id=env_id).first()
    if not env:
        raise HTTPException(404, detail="Environment not found")
    db.delete(env)
    db.commit()
