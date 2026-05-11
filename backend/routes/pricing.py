"""
Pricing routes — expose model pricing table and cost estimation,
plus per-user custom pricing overrides.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import ModelPricing, User
from backend.database import get_db
from backend.routes.auth import get_current_user
from backend.pricing import estimate_cost, get_all_models, get_model_info
import uuid

router = APIRouter()


# ── Global pricing table ─────────────────────────────────────────────────────

@router.get("")
async def list_models():
    """Return pricing for all known models."""
    return get_all_models()


@router.get("/model")
async def get_model_pricing(model: str = Query(..., description="Model name")):
    """Return pricing for a specific model."""
    info = get_model_info(model)
    if info is None:
        return {"model": model, "known": False, "message": "Model not in pricing table"}
    return {**info, "known": True}


@router.get("/estimate")
async def estimate_trace_cost(
    model: str = Query(..., description="Model name"),
    prompt_tokens: int = Query(0, ge=0),
    completion_tokens: int = Query(0, ge=0),
    total_tokens: int = Query(0, ge=0, description="Used if prompt/completion not provided"),
):
    """
    Estimate cost for a single LLM call.

    Provide (prompt_tokens + completion_tokens) for exact pricing,
    or just total_tokens for an approximate estimate (75/25 split assumed).
    """
    cost = estimate_cost(
        model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    info = get_model_info(model)
    return {
        "model": model,
        "prompt_tokens": prompt_tokens or int(total_tokens * 0.75),
        "completion_tokens": completion_tokens or (total_tokens - int(total_tokens * 0.75)),
        "total_tokens": total_tokens or (prompt_tokens + completion_tokens),
        "estimated_cost_usd": cost,
        "known_model": info is not None,
        "pricing": info,
    }


# ── Custom per-user pricing ──────────────────────────────────────────────────

class CustomPricingIn(BaseModel):
    model: str
    provider: Optional[str] = None
    prompt_cost_per_1k: float
    completion_cost_per_1k: float
    is_free: bool = False
    notes: Optional[str] = None


class CustomPricingOut(BaseModel):
    id: str
    model: str
    provider: Optional[str]
    prompt_cost_per_1k: float
    completion_cost_per_1k: float
    is_free: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


@router.get("/custom", response_model=List[CustomPricingOut])
async def list_custom_pricing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all custom pricing overrides for the current user."""
    rows = db.query(ModelPricing).filter(ModelPricing.user_id == current_user.id).all()
    return [
        CustomPricingOut(
            id=r.id,
            model=r.model,
            provider=r.provider,
            prompt_cost_per_1k=float(r.prompt_cost_per_1k),
            completion_cost_per_1k=float(r.completion_cost_per_1k),
            is_free=r.is_free,
            notes=r.notes,
        )
        for r in rows
    ]


@router.post("/custom", response_model=CustomPricingOut, status_code=201)
async def upsert_custom_pricing(
    body: CustomPricingIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a custom pricing override for a model."""
    existing = db.query(ModelPricing).filter(
        ModelPricing.user_id == current_user.id,
        ModelPricing.model == body.model,
    ).first()

    if existing:
        existing.provider = body.provider
        existing.prompt_cost_per_1k = body.prompt_cost_per_1k
        existing.completion_cost_per_1k = body.completion_cost_per_1k
        existing.is_free = body.is_free
        existing.notes = body.notes
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = ModelPricing(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            model=body.model,
            provider=body.provider,
            prompt_cost_per_1k=body.prompt_cost_per_1k,
            completion_cost_per_1k=body.completion_cost_per_1k,
            is_free=body.is_free,
            notes=body.notes,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    return CustomPricingOut(
        id=row.id,
        model=row.model,
        provider=row.provider,
        prompt_cost_per_1k=float(row.prompt_cost_per_1k),
        completion_cost_per_1k=float(row.completion_cost_per_1k),
        is_free=row.is_free,
        notes=row.notes,
    )


@router.delete("/custom/{model_name}", status_code=204)
async def delete_custom_pricing(
    model_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a custom pricing override."""
    row = db.query(ModelPricing).filter(
        ModelPricing.user_id == current_user.id,
        ModelPricing.model == model_name,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Custom pricing not found")
    db.delete(row)
    db.commit()
