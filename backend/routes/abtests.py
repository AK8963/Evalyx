"""
A/B Testing routes — compare prompt/model configurations in production.
Mirrors TraceIQ experiment comparison functionality.
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import ABTest, User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ABVariant(BaseModel):
    name: str
    prompt_id: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    weight: float = 0.5          # Traffic split weight (0–1), sums to 1 across variants


class ABTestCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    variants: List[ABVariant]    # At least 2 variants required


class ABTestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None     # 'running', 'paused', 'completed'
    winner_variant: Optional[str] = None
    end_date: Optional[datetime] = None


def _ab_dict(ab: ABTest) -> dict:
    return {
        "id": ab.id,
        "project_id": ab.project_id,
        "name": ab.name,
        "description": ab.description,
        "variants": ab.variants or [],
        "status": ab.status,
        "winner_variant": ab.winner_variant,
        "start_date": ab.start_date.isoformat() if ab.start_date else None,
        "end_date": ab.end_date.isoformat() if ab.end_date else None,
        "created_at": ab.created_at.isoformat() if ab.created_at else None,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/", status_code=201)
def create_ab_test(
    payload: ABTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an A/B test comparing two or more prompt/model configurations."""
    if len(payload.variants) < 2:
        raise HTTPException(400, detail="At least 2 variants required")

    ab = ABTest(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        variants=[v.model_dump() for v in payload.variants],
        status="running",
    )
    db.add(ab)
    db.commit()
    db.refresh(ab)
    return _ab_dict(ab)


@router.get("/")
def list_ab_tests(
    project_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all A/B tests for a project."""
    q = db.query(ABTest).filter_by(project_id=project_id)
    if status:
        q = q.filter(ABTest.status == status)
    tests = q.order_by(ABTest.created_at.desc()).all()
    return [_ab_dict(t) for t in tests]


@router.get("/{test_id}")
def get_ab_test(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ab = db.query(ABTest).filter_by(id=test_id).first()
    if not ab:
        raise HTTPException(404, detail="A/B test not found")
    return _ab_dict(ab)


@router.patch("/{test_id}")
def update_ab_test(
    test_id: str,
    payload: ABTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ab = db.query(ABTest).filter_by(id=test_id).first()
    if not ab:
        raise HTTPException(404, detail="A/B test not found")

    valid_statuses = {"running", "paused", "completed"}
    if payload.status and payload.status not in valid_statuses:
        raise HTTPException(400, detail=f"status must be one of: {', '.join(valid_statuses)}")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ab, field, value)
    db.commit()
    db.refresh(ab)
    return _ab_dict(ab)


@router.delete("/{test_id}", status_code=204)
def delete_ab_test(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ab = db.query(ABTest).filter_by(id=test_id).first()
    if not ab:
        raise HTTPException(404, detail="A/B test not found")
    db.delete(ab)
    db.commit()


@router.post("/{test_id}/assign")
def assign_variant(
    test_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Randomly assign a variant for a request using weighted sampling.
    Returns the variant config to use for this request.
    """
    import random

    ab = db.query(ABTest).filter_by(id=test_id, status="running").first()
    if not ab:
        raise HTTPException(404, detail="Active A/B test not found")

    variants = ab.variants or []
    if not variants:
        raise HTTPException(400, detail="No variants configured")

    weights = [v.get("weight", 1.0 / len(variants)) for v in variants]
    total = sum(weights) or 1
    weights = [w / total for w in weights]

    chosen = random.choices(variants, weights=weights, k=1)[0]
    return {"test_id": test_id, "assigned_variant": chosen}
