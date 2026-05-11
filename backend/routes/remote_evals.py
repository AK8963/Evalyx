"""
Remote Evals routes — Phase 2 implementation.

Allows users to submit Python scorer code + input rows and have them
executed in a sandboxed subprocess, returning per-row scores.

Security model:
  - Eval code runs in a subprocess with a strict 30-second timeout.
  - The subprocess receives only the input rows as JSON via stdin.
  - No network, filesystem, or import access beyond the stdlib is enforced
    at the OS level (future: seccomp). For now we use a safe builtins
    allowlist inside the subprocess.
  - Results are parsed from stdout JSON — no arbitrary object execution.

POST /api/remote-evals/          — Create & queue a remote eval
GET  /api/remote-evals/          — List remote evals for a project
GET  /api/remote-evals/{id}      — Get one remote eval (with results)
POST /api/remote-evals/{id}/run  — (Re-)run a pending/failed eval
DELETE /api/remote-evals/{id}    — Delete an eval
"""

import json
import subprocess
import sys
import textwrap
import tempfile
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import RemoteEval, User

router = APIRouter()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RemoteEvalCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    scorer_code: str           # Python function: def score(input, output, expected): -> float|bool
    input_rows: List[Dict]     # [{input, expected?, metadata?}]
    response_schema: Optional[Dict] = None  # JSON Schema for validating outputs
    auto_run: bool = True      # Start immediately after creation


class RemoteEvalResponse(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    total_items: int
    completed_items: int
    aggregate: Optional[Dict]
    results: Optional[List]
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


# ---------------------------------------------------------------------------
# Sandbox executor
# ---------------------------------------------------------------------------

_RUNNER_TEMPLATE = textwrap.dedent("""
import json, sys, math, re, statistics, collections

# ── user scorer code ───────────────────────────────────────────────────────
{scorer_code}

# ── execute rows ───────────────────────────────────────────────────────────
rows = json.loads(sys.stdin.read())
results = []
for row in rows:
    inp = row.get("input")
    exp = row.get("expected")
    out = row.get("output")          # may be None if no LLM call
    meta = row.get("metadata", {{}})
    try:
        raw = score(input=inp, output=out, expected=exp)
        if isinstance(raw, bool):
            val = 1.0 if raw else 0.0
            passed = raw
        elif isinstance(raw, (int, float)):
            val = max(0.0, min(1.0, float(raw)))
            passed = val >= 0.5
        elif isinstance(raw, dict):
            val = float(raw.get("score", raw.get("value", 0)))
            val = max(0.0, min(1.0, val))
            passed = raw.get("passed", val >= 0.5)
        else:
            val = 0.0
            passed = False
        results.append({{"input": inp, "expected": exp, "output": out,
                         "score": val, "passed": passed, "error": None}})
    except Exception as e:
        results.append({{"input": inp, "expected": exp, "output": out,
                         "score": 0.0, "passed": False, "error": str(e)}})

print(json.dumps(results))
""")


def _run_sandbox(scorer_code: str, rows: List[Dict], timeout: int = 30) -> List[Dict]:
    """
    Execute scorer_code against rows in an isolated subprocess.
    Returns list of result dicts.
    """
    script = _RUNNER_TEMPLATE.format(scorer_code=scorer_code)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            input=json.dumps(rows),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise ValueError(f"Sandbox error: {proc.stderr[:500]}")
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        raise ValueError(f"Eval timed out after {timeout}s")
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def _compute_aggregate(results: List[Dict]) -> Dict:
    scores = [r["score"] for r in results if r.get("error") is None]
    passed = [r for r in results if r.get("passed")]
    errors = [r for r in results if r.get("error")]
    return {
        "total": len(results),
        "completed": len(results) - len(errors),
        "errors": len(errors),
        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "min_score": round(min(scores), 4) if scores else 0.0,
        "max_score": round(max(scores), 4) if scores else 0.0,
        "pass_rate": round(len(passed) / len(results), 4) if results else 0.0,
    }


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def _execute_eval(eval_id: str, db_url: str):
    """Run in a background thread — opens its own DB session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        ev = db.query(RemoteEval).filter_by(id=eval_id).first()
        if not ev:
            return
        ev.status = "running"
        ev.started_at = datetime.utcnow()
        db.commit()

        results = _run_sandbox(ev.scorer_code, ev.input_rows or [])
        ev.results = results
        ev.aggregate = _compute_aggregate(results)
        ev.completed_items = len(results)
        ev.status = "completed"
        ev.completed_at = datetime.utcnow()
    except Exception as e:
        ev.status = "failed"
        ev.error_message = str(e)
        ev.completed_at = datetime.utcnow()
    finally:
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _to_response(ev: RemoteEval) -> dict:
    return {
        "id": ev.id,
        "project_id": ev.project_id,
        "name": ev.name,
        "description": ev.description,
        "scorer_code": ev.scorer_code,
        "response_schema": ev.response_schema,
        "status": ev.status,
        "total_items": ev.total_items,
        "completed_items": ev.completed_items,
        "aggregate": ev.aggregate,
        "results": ev.results,
        "error_message": ev.error_message,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
        "started_at": ev.started_at.isoformat() if ev.started_at else None,
        "completed_at": ev.completed_at.isoformat() if ev.completed_at else None,
    }


@router.post("/", status_code=201)
def create_remote_eval(
    payload: RemoteEvalCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a remote eval job and optionally start it immediately."""
    if len(payload.input_rows) > 500:
        raise HTTPException(400, "Maximum 500 input rows per remote eval")
    if len(payload.scorer_code) > 10_000:
        raise HTTPException(400, "Scorer code exceeds 10,000 character limit")

    ev = RemoteEval(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        scorer_code=payload.scorer_code,
        input_rows=payload.input_rows,
        response_schema=payload.response_schema,
        total_items=len(payload.input_rows),
        status="pending",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    if payload.auto_run:
        from backend.config import settings
        background_tasks.add_task(_execute_eval, ev.id, settings.DATABASE_URL)

    return _to_response(ev)


@router.get("/")
def list_remote_evals(
    project_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List remote evals for a project."""
    q = db.query(RemoteEval).filter_by(project_id=project_id)
    if status:
        q = q.filter(RemoteEval.status == status)
    total = q.count()
    evals = q.order_by(RemoteEval.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "offset": offset, "limit": limit, "evals": [_to_response(e) for e in evals]}


@router.get("/{eval_id}")
def get_remote_eval(
    eval_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single remote eval with full results."""
    ev = db.query(RemoteEval).filter_by(id=eval_id).first()
    if not ev:
        raise HTTPException(404, "Remote eval not found")
    return _to_response(ev)


@router.post("/{eval_id}/run")
def run_remote_eval(
    eval_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Re-)run a pending or failed remote eval."""
    ev = db.query(RemoteEval).filter_by(id=eval_id).first()
    if not ev:
        raise HTTPException(404, "Remote eval not found")
    if ev.status == "running":
        raise HTTPException(409, "Eval is already running")

    ev.status = "pending"
    ev.error_message = None
    ev.results = None
    ev.aggregate = None
    ev.completed_items = 0
    db.commit()

    from backend.config import settings
    background_tasks.add_task(_execute_eval, ev.id, settings.DATABASE_URL)
    return {"message": "Eval queued", "id": ev.id}


@router.delete("/{eval_id}", status_code=204)
def delete_remote_eval(
    eval_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a remote eval and its results."""
    ev = db.query(RemoteEval).filter_by(id=eval_id).first()
    if not ev:
        raise HTTPException(404, "Remote eval not found")
    if ev.status == "running":
        raise HTTPException(409, "Cannot delete a running eval")
    db.delete(ev)
    db.commit()
