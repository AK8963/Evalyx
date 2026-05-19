"""
Metrics routes â€” CRUD for named scorer definitions (built-in + custom).
"""

import math
import re as _re
import json as _json
import statistics as _statistics
import difflib as _difflib
import concurrent.futures
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from backend.scoring import run_autoeval, AUTOEVAL_REGISTRY
from database.models import Metric, User

router = APIRouter()

_BUILTINS = [
    {
        "name": "Correctness",
        "description": "Evaluates factual accuracy of the answer against the question.",
        "metric_type": "llm_judge",
        "prompt_template": (
            "You are an impartial judge evaluating an AI assistant's factual accuracy.\n\n"
            "Question: {input}\nAnswer: {output}\n\n"
            "Rate the factual correctness of the answer on a scale from 0 to 1.\n"
            "- 1.0 = completely accurate, no errors\n"
            "- 0.5 = partially correct, minor errors or omissions\n"
            "- 0.0 = factually wrong or completely off-topic\n\n"
            "Respond with EXACTLY:\nSCORE: [number between 0 and 1]\n"
            "EXPLANATION: [one or two sentences explaining your reasoning]"
        ),
        "is_builtin": True,
    },
    {
        "name": "Relevance",
        "description": "Evaluates how on-topic and relevant the answer is to the question.",
        "metric_type": "llm_judge",
        "prompt_template": (
            "You are an impartial judge evaluating an AI assistant's response relevance.\n\n"
            "Question: {input}\nAnswer: {output}\n\n"
            "Rate how relevant and on-topic the answer is to the question on a scale from 0 to 1.\n"
            "- 1.0 = directly answers the question with no off-topic content\n"
            "- 0.5 = partially relevant, goes off-topic or misses part of the question\n"
            "- 0.0 = entirely irrelevant, does not address the question\n\n"
            "Respond with EXACTLY:\nSCORE: [number between 0 and 1]\n"
            "EXPLANATION: [one or two sentences explaining your reasoning]"
        ),
        "is_builtin": True,
    },
    {
        "name": "Clarity",
        "description": "Evaluates how clear, readable, and well-structured the answer is.",
        "metric_type": "llm_judge",
        "prompt_template": (
            "You are an impartial judge evaluating an AI assistant's communication clarity.\n\n"
            "Question: {input}\nAnswer: {output}\n\n"
            "Rate how clear, readable, and well-structured the answer is on a scale from 0 to 1.\n"
            "- 1.0 = extremely clear, easy to understand, well-organized\n"
            "- 0.5 = somewhat clear but could be improved in structure or phrasing\n"
            "- 0.0 = confusing, hard to parse, or poorly written\n\n"
            "Respond with EXACTLY:\nSCORE: [number between 0 and 1]\n"
            "EXPLANATION: [one or two sentences explaining your reasoning]"
        ),
        "is_builtin": True,
    },
]


def _ensure_builtins(db: Session):
    """Seed built-in metrics if they don't exist yet."""
    for b in _BUILTINS:
        existing = db.query(Metric).filter(Metric.name == b["name"], Metric.is_builtin == True).first()
        if not existing:
            db.add(Metric(
                name=b["name"],
                description=b["description"],
                metric_type=b["metric_type"],
                prompt_template=b["prompt_template"],
                is_builtin=True,
                project_id=None,
            ))
        elif existing.metric_type == "ollama":
            existing.metric_type = "llm_judge"
    db.commit()


def _metric_dict(m: Metric) -> dict:
    mt = m.metric_type
    if mt == "ollama":
        mt = "llm_judge"
    return {
        "id": m.id,
        "project_id": m.project_id,
        "name": m.name,
        "description": m.description,
        "metric_type": mt,
        "prompt_template": m.prompt_template,
        "config": m.config or {},
        "is_builtin": m.is_builtin,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ---------------------------------------------------------------------------
# Safe formula evaluator
# ---------------------------------------------------------------------------

_FORMULA_SAFE_GLOBALS = {
    "__builtins__": {},
    "abs": abs, "round": round, "min": min, "max": max,
    "len": len, "int": int, "float": float, "str": str, "bool": bool,
    "math": math,
}


def _eval_formula(expression: str, input_val: Any, output_val: Any, expected_val: Any) -> dict:
    ctx = {**_FORMULA_SAFE_GLOBALS, "input": input_val, "output": output_val, "expected": expected_val}
    result = eval(expression, {"__builtins__": {}}, ctx)  # noqa: S307
    if isinstance(result, bool):
        score = 1.0 if result else 0.0
    else:
        score = max(0.0, min(1.0, float(result)))
    return {"score": round(score, 4), "explanation": f"Formula result: {result}"}


# ---------------------------------------------------------------------------
# Safe code snippet executor
# ---------------------------------------------------------------------------

_CODE_SAFE_BUILTINS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "len": len, "int": int, "float": float, "str": str, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "range": range, "enumerate": enumerate, "zip": zip,
    "isinstance": isinstance, "type": type, "sum": sum, "sorted": sorted,
    "any": any, "all": all, "map": map, "filter": filter,
}

_CODE_SAFE_GLOBALS = {
    "__builtins__": _CODE_SAFE_BUILTINS,
    "math": math, "re": _re, "json": _json,
    "statistics": _statistics, "difflib": _difflib,
}


def _exec_snippet(snippet: str, input_val: Any, output_val: Any, expected_val: Any, timeout_s: int = 10) -> dict:
    def _run():
        local_vars: dict = {}
        exec(snippet, dict(_CODE_SAFE_GLOBALS), local_vars)  # noqa: S102
        score_fn = local_vars.get("score")
        if not callable(score_fn):
            raise ValueError("Snippet must define a function named 'score'")
        result = score_fn(input=input_val, output=output_val, expected=expected_val, metadata={})
        if isinstance(result, (int, float)):
            return {"score": max(0.0, min(1.0, float(result))), "explanation": ""}
        if isinstance(result, dict):
            result.setdefault("explanation", "")
            result["score"] = max(0.0, min(1.0, float(result.get("score", 0))))
            return result
        raise ValueError(f"score() must return a float or dict, got {type(result)}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Code execution timed out after {timeout_s}s")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MetricCreate(BaseModel):
    name: str
    description: Optional[str] = None
    metric_type: str = "llm_judge"
    prompt_template: Optional[str] = None
    config: Optional[Dict] = None
    project_id: Optional[str] = None


class MetricUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_template: Optional[str] = None
    config: Optional[Dict] = None


class MetricTestRequest(BaseModel):
    metric_type: str
    config: Dict = {}
    input: Any = ""
    output: Any = ""
    expected: Any = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_metrics(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all metrics â€” built-in globals + custom for this project."""
    _ensure_builtins(db)
    q = db.query(Metric).filter(
        (Metric.is_builtin == True) |
        ((Metric.project_id == project_id) if project_id else (Metric.is_builtin == False))
    ).order_by(Metric.is_builtin.desc(), Metric.created_at)
    return [_metric_dict(m) for m in q.all()]


@router.post("/test")
async def test_metric(
    payload: MetricTestRequest,
    current_user: User = Depends(get_current_user),
):
    """Test any metric type against sample input/output/expected. Returns score + explanation."""
    mt = payload.metric_type
    cfg = payload.config or {}
    start = time.perf_counter()

    try:
        if mt in ("llm_judge", "ollama"):
            from backend.scoring import score_single_trace
            import types as _types
            prompt_template = cfg.get("prompt_template", "{input}\n{output}")
            model = cfg.get("model", "llama3")
            fake_trace = _types.SimpleNamespace(
                input_data=payload.input,
                output_data=payload.output,
                expected_output=payload.expected,
            )
            result = await score_single_trace(fake_trace, "test", model, prompt_template)

        elif mt == "autoeval":
            scorer_name = cfg.get("scorer")
            if not scorer_name:
                raise ValueError("autoeval config must include 'scorer'")
            if scorer_name not in AUTOEVAL_REGISTRY:
                raise ValueError(f"Unknown scorer: {scorer_name}")
            scorer_cfg = {k: v for k, v in cfg.items() if k != "scorer"}
            result = run_autoeval(
                scorer_name=scorer_name,
                output=payload.output,
                expected=payload.expected,
                input_data=payload.input,
                config=scorer_cfg,
            )

        elif mt == "formula":
            expression = cfg.get("expression", "")
            if not expression:
                raise ValueError("formula config must include 'expression'")
            result = _eval_formula(expression, payload.input, payload.output, payload.expected)

        elif mt == "code":
            snippet = cfg.get("snippet", "")
            if not snippet:
                raise ValueError("code config must include 'snippet'")
            timeout_s = int(cfg.get("timeout_s", 10))
            result = _exec_snippet(snippet, payload.input, payload.output, payload.expected, timeout_s)

        else:
            raise ValueError(f"Unknown metric_type: {mt}")

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"score": result.get("score", 0), "explanation": result.get("explanation", ""), "latency_ms": latency_ms}

    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("", status_code=201)
def create_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom metric."""
    mt = payload.metric_type if payload.metric_type != "ollama" else "llm_judge"
    m = Metric(
        name=payload.name,
        description=payload.description,
        metric_type=mt,
        prompt_template=payload.prompt_template,
        config=payload.config or {},
        project_id=payload.project_id,
        is_builtin=False,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return _metric_dict(m)


@router.put("/{metric_id}")
def update_metric(
    metric_id: str,
    payload: MetricUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a custom metric (built-ins cannot be modified)."""
    m = db.query(Metric).filter(Metric.id == metric_id).first()
    if not m:
        raise HTTPException(404, "Metric not found")
    if m.is_builtin:
        raise HTTPException(403, "Built-in metrics cannot be modified")
    if payload.name is not None:
        m.name = payload.name
    if payload.description is not None:
        m.description = payload.description
    if payload.prompt_template is not None:
        m.prompt_template = payload.prompt_template
    if payload.config is not None:
        m.config = payload.config
    m.updated_at = datetime.utcnow()
    db.commit()
    return _metric_dict(m)


@router.delete("/{metric_id}", status_code=204)
def delete_metric(
    metric_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom metric (built-ins cannot be deleted)."""
    m = db.query(Metric).filter(Metric.id == metric_id).first()
    if not m:
        raise HTTPException(404, "Metric not found")
    if m.is_builtin:
        raise HTTPException(403, "Built-in metrics cannot be deleted")
    db.delete(m)
    db.commit()

