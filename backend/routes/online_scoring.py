"""
Online scoring routes — automatic production trace scoring rules.
"""



import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import OnlineScoringRule, Score, Trace, User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RuleCreate(BaseModel):
    project_id: str
    name: str
    scorer_type: str            # 'llm', 'code', 'expected'
    scorer_config: Dict         # {prompt_template, model, ...}
    sample_rate: float = 1.0
    filter_conditions: Optional[Dict] = None


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    scorer_config: Optional[Dict] = None
    sample_rate: Optional[float] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------

@router.post("/rules", status_code=201)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = OnlineScoringRule(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        scorer_type=payload.scorer_type,
        scorer_config=payload.scorer_config,
        sample_rate=payload.sample_rate,
        filter_conditions=payload.filter_conditions,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_dict(rule)


@router.get("/rules")
def list_rules(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rules = db.query(OnlineScoringRule).filter_by(project_id=project_id).all()
    return [_rule_dict(r) for r in rules]


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(OnlineScoringRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    for field, val in payload.dict(exclude_none=True).items():
        setattr(rule, field, val)
    db.commit()
    return _rule_dict(rule)


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(OnlineScoringRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Manual score trigger
# ---------------------------------------------------------------------------

@router.post("/score/{trace_id}")
def score_trace(
    trace_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger online scoring for a specific trace."""
    trace = db.query(Trace).filter_by(id=trace_id).first()
    if not trace:
        raise HTTPException(404, "Trace not found")

    rules = (
        db.query(OnlineScoringRule)
        .filter_by(project_id=trace.project_id, is_active=True)
        .all()
    )

    if not rules:
        return {"message": "No active scoring rules for this project", "scored": 0}

    background_tasks.add_task(_run_scoring, trace_id, [r.id for r in rules])
    return {"message": "Scoring queued", "rules_applied": len(rules), "trace_id": trace_id}


# ---------------------------------------------------------------------------
# Background scoring task
# ---------------------------------------------------------------------------

def _run_scoring(trace_id: str, rule_ids: List[str]) -> None:
    """Apply scoring rules to a trace in the background."""
    import random
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        trace = db.query(Trace).filter_by(id=trace_id).first()
        if not trace:
            return

        for rule_id in rule_ids:
            rule = db.query(OnlineScoringRule).filter_by(id=rule_id).first()
            if not rule or not rule.is_active:
                continue

            # Sample rate check
            if random.random() > rule.sample_rate:
                continue

            score_value = _apply_scorer(rule, trace, db)
            if score_value is not None:
                score = Score(
                    trace_id=trace_id,
                    project_id=trace.project_id,
                    scorer_name=rule.name,
                    scorer_type=rule.scorer_type,
                    score_value=score_value,
                    scorer_config=rule.scorer_config,
                )
                db.add(score)

        db.commit()
    except Exception as exc:
        logger.error("Online scoring failed for trace %s: %s", trace_id, exc)
    finally:
        db.close()


def _apply_scorer(rule: OnlineScoringRule, trace: Trace, db) -> Optional[float]:
    """Dispatch to appropriate scorer and return 0-1 float."""
    try:
        if rule.scorer_type == "expected":
            if trace.expected_output and trace.output_data:
                out = str(trace.output_data)
                exp = str(trace.expected_output)
                return 1.0 if out.strip() == exp.strip() else (0.5 if exp in out else 0.0)
            return None

        if rule.scorer_type == "code":
            code = rule.scorer_config.get("code", "")
            if code:
                namespace: Dict = {}
                exec(code, namespace)  # noqa: S102
                fn = namespace.get("score")
                if callable(fn):
                    val = fn(
                        input=trace.input_data,
                        output=trace.output_data,
                        expected=trace.expected_output,
                    )
                    return float(val)
            return None

        # LLM scorer — placeholder (full impl in backend/scoring.py)
        return None

    except Exception as exc:
        logger.warning("Scorer %s failed: %s", rule.name, exc)
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_dict(r: OnlineScoringRule) -> Dict:
    return {
        "id": r.id,
        "project_id": r.project_id,
        "name": r.name,
        "scorer_type": r.scorer_type,
        "scorer_config": r.scorer_config,
        "sample_rate": r.sample_rate,
        "filter_conditions": r.filter_conditions,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
