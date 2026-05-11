"""
Experiments routes — immutable eval snapshots with per-item results and comparison.
"""



import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import (
    Dataset, DatasetItem, Experiment, ExperimentResult, User
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ExperimentCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    dataset_id: Optional[str] = None
    model: Optional[str] = None
    task_config: Dict = {}
    scorer_configs: List[Dict] = []


class ExperimentResultCreate(BaseModel):
    experiment_id: str
    input_data: Optional[Any] = None
    actual_output: Optional[Any] = None
    expected_output: Optional[Any] = None
    scores: Dict = {}
    overall_score: Optional[float] = None
    latency_ms: Optional[float] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Experiment CRUD
# ---------------------------------------------------------------------------

@router.post("/", status_code=201)
def create_experiment(
    payload: ExperimentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exp = Experiment(
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        dataset_id=payload.dataset_id,
        model=payload.model,
        task_config=payload.task_config,
        scorer_configs=payload.scorer_configs,
        created_by=current_user.id,
        status="pending",
    )
    if payload.dataset_id:
        count = db.query(DatasetItem).filter_by(dataset_id=payload.dataset_id).count()
        exp.total_items = count

    db.add(exp)
    db.commit()
    db.refresh(exp)

    # Kick off background scoring if dataset provided
    if payload.dataset_id and payload.scorer_configs:
        background_tasks.add_task(_run_experiment, exp.id)

    return _exp_dict(exp)


@router.get("/")
def list_experiments(
    project_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exps = (
        db.query(Experiment)
        .filter_by(project_id=project_id)
        .order_by(Experiment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_exp_dict(e) for e in exps]


@router.get("/{exp_id}")
def get_experiment(
    exp_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exp = _get_or_404(db, exp_id)
    return _exp_dict(exp)


@router.get("/{exp_id}/results")
def get_experiment_results(
    exp_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_or_404(db, exp_id)
    results = (
        db.query(ExperimentResult)
        .filter_by(experiment_id=exp_id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_result_dict(r) for r in results]


@router.post("/{exp_id}/results", status_code=201)
def add_result(
    exp_id: str,
    payload: ExperimentResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a single result row — used by SDK-driven eval runs."""
    exp = _get_or_404(db, exp_id)
    if exp.is_locked:
        raise HTTPException(409, "Experiment is locked and cannot receive new results")

    result = ExperimentResult(
        experiment_id=exp_id,
        input_data=payload.input_data,
        actual_output=payload.actual_output,
        expected_output=payload.expected_output,
        scores=payload.scores,
        overall_score=payload.overall_score,
        latency_ms=payload.latency_ms,
        tokens_used=payload.tokens_used,
        cost_usd=payload.cost_usd,
        error_message=payload.error_message,
        model=exp.model,
    )
    db.add(result)
    exp.completed_items = (exp.completed_items or 0) + 1
    if exp.status == "pending":
        exp.status = "running"
    db.commit()
    return _result_dict(result)


@router.post("/{exp_id}/lock")
def lock_experiment(
    exp_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lock an experiment — finalise aggregate scores and prevent further edits."""
    exp = _get_or_404(db, exp_id)
    _finalise_experiment(db, exp)
    exp.is_locked = True
    exp.status = "completed"
    db.commit()
    return _exp_dict(exp)


@router.get("/compare")
def compare_experiments(
    exp_ids: str = Query(..., description="Comma-separated experiment IDs"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare aggregate scores across multiple experiments."""
    ids = [i.strip() for i in exp_ids.split(",") if i.strip()]
    exps = db.query(Experiment).filter(Experiment.id.in_(ids)).all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "model": e.model,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "aggregate_scores": e.aggregate_scores or {},
            "completed_items": e.completed_items,
            "status": e.status,
        }
        for e in exps
    ]


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def _run_experiment(exp_id: str) -> None:
    """
    Placeholder background runner.
    In production this is handled by a Celery worker.
    Here we just mark the experiment as running.
    """
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        exp = db.query(Experiment).filter_by(id=exp_id).first()
        if exp:
            exp.status = "running"
            db.commit()
    except Exception as exc:
        logger.error("Background experiment runner failed: %s", exc)
    finally:
        db.close()


def _finalise_experiment(db: Session, exp: Experiment) -> None:
    """Compute aggregate scores from ExperimentResult rows."""
    from sqlalchemy import func

    results = db.query(ExperimentResult).filter_by(experiment_id=exp.id).all()
    if not results:
        return

    # Collect all scorer names
    scorer_names: set = set()
    for r in results:
        scorer_names.update((r.scores or {}).keys())

    aggregates: Dict = {}
    for sn in scorer_names:
        vals = [
            r.scores[sn].get("score", r.scores[sn]) if isinstance(r.scores.get(sn), dict) else r.scores.get(sn)
            for r in results
            if r.scores and sn in r.scores
        ]
        numeric = [v for v in vals if isinstance(v, (int, float))]
        if numeric:
            aggregates[sn] = round(sum(numeric) / len(numeric), 4)

    exp.aggregate_scores = aggregates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, exp_id: str) -> Experiment:
    exp = db.query(Experiment).filter_by(id=exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")
    return exp


def _exp_dict(e: Experiment) -> Dict:
    return {
        "id": e.id,
        "project_id": e.project_id,
        "name": e.name,
        "description": e.description,
        "model": e.model,
        "dataset_id": e.dataset_id,
        "status": e.status,
        "total_items": e.total_items,
        "completed_items": e.completed_items,
        "aggregate_scores": e.aggregate_scores,
        "is_locked": e.is_locked,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
    }


def _result_dict(r: ExperimentResult) -> Dict:
    return {
        "id": r.id,
        "experiment_id": r.experiment_id,
        "input_data": r.input_data,
        "actual_output": r.actual_output,
        "expected_output": r.expected_output,
        "scores": r.scores,
        "overall_score": r.overall_score,
        "latency_ms": r.latency_ms,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ---------------------------------------------------------------------------
# Regression Detection
# ---------------------------------------------------------------------------

@router.get("/{exp_id}/regression")
def detect_regression(
    exp_id: str,
    baseline_id: str = Query(..., description="ID of the baseline experiment to compare against"),
    threshold: float = Query(0.05, ge=0.0, le=1.0, description="Min score drop to count as regression (0.05 = 5%)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compare this experiment's aggregate scores against a baseline experiment.
    Returns regressions (score drops) and improvements per scorer.
    """
    current = _get_or_404(db, exp_id)
    baseline = _get_or_404(db, baseline_id)

    current_scores: Dict = current.aggregate_scores or {}
    baseline_scores: Dict = baseline.aggregate_scores or {}

    all_scorers = set(current_scores.keys()) | set(baseline_scores.keys())

    regressions = []
    improvements = []
    stable = []

    for scorer in sorted(all_scorers):
        cur = current_scores.get(scorer)
        bas = baseline_scores.get(scorer)

        if cur is None or bas is None:
            continue  # Can't compare if one side is missing

        drop = bas - cur          # Positive = regression (score went down)
        change_pct = drop / bas if bas > 0 else 0.0

        entry = {
            "scorer": scorer,
            "baseline": round(float(bas), 4),
            "current": round(float(cur), 4),
            "delta": round(float(cur - bas), 4),    # Positive = improved
            "delta_pct": round(float(-change_pct) * 100, 2),  # Positive % = improved
        }

        if drop > threshold:
            severity = "critical" if change_pct > 0.15 else ("high" if change_pct > 0.10 else "medium")
            entry["severity"] = severity
            regressions.append(entry)
        elif -drop > threshold:
            improvements.append(entry)
        else:
            stable.append(entry)

    overall_has_regression = len(regressions) > 0
    worst_regression = max(regressions, key=lambda x: -x["delta"]) if regressions else None

    return {
        "experiment_id": exp_id,
        "baseline_id": baseline_id,
        "experiment_name": current.name,
        "baseline_name": baseline.name,
        "threshold": threshold,
        "has_regression": overall_has_regression,
        "regressions": regressions,
        "improvements": improvements,
        "stable": stable,
        "worst_regression": worst_regression,
        "summary": {
            "regressed_scorers": len(regressions),
            "improved_scorers": len(improvements),
            "stable_scorers": len(stable),
            "total_scorers": len(all_scorers),
        },
    }
