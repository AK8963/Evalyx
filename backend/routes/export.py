"""
Data Export routes — export traces, datasets, and experiment results.
Mirrors TraceIQ: https://www.traciq.dev/docs/annotate/export
"""

import csv
import io
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import DatasetItem, Experiment, ExperimentResult, Trace, User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    for row in rows:
        # Flatten JSON fields to strings for CSV
        flat = {k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else v) for k, v in row.items()}
        writer.writerow(flat)
    return buf.getvalue()


def _csv_response(data: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _json_response(data, filename: str) -> Response:
    return Response(
        content=json.dumps(data, default=str, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Traces export
# ---------------------------------------------------------------------------

@router.get("/traces")
def export_traces(
    project_id: str,
    format: str = Query("json", pattern="^(json|csv|jsonl)$"),
    limit: int = Query(1000, le=10000),
    status: Optional[str] = None,
    model: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export project traces as JSON, JSONL, or CSV.
    Mirrors TraceIQ /v1/project_logs/{project_id}/fetch.
    """
    q = db.query(Trace).filter_by(project_id=project_id)
    if status:
        q = q.filter(Trace.status == status)
    if model:
        q = q.filter(Trace.model == model)
    traces = q.order_by(Trace.timestamp.desc()).limit(limit).all()

    rows = [
        {
            "id": t.id,
            "project_id": t.project_id,
            "model": t.model,
            "status": t.status,
            "input": t.input_data,
            "output": t.output_data,
            "expected": t.expected_output,
            "prompt_tokens": t.prompt_tokens,
            "completion_tokens": t.completion_tokens,
            "total_tokens": t.total_tokens,
            "latency_ms": t.latency_ms,
            "cost_usd": float(t.cost_usd) if t.cost_usd else None,
            "tags": t.tags,
            "metadata": t.meta,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        }
        for t in traces
    ]

    if format == "csv":
        return _csv_response(_as_csv(rows), f"traces_{project_id}.csv")
    if format == "jsonl":
        content = "\n".join(json.dumps(r, default=str) for r in rows)
        return Response(
            content=content,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="traces_{project_id}.jsonl"'},
        )
    return _json_response(rows, f"traces_{project_id}.json")


# ---------------------------------------------------------------------------
# Dataset export
# ---------------------------------------------------------------------------

@router.get("/datasets/{dataset_id}")
def export_dataset(
    dataset_id: str,
    format: str = Query("json", pattern="^(json|csv|jsonl)$"),
    split: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export dataset items as JSON, JSONL, or CSV.
    Mirrors TraceIQ /v1/dataset/{dataset_id}/fetch.
    """
    q = db.query(DatasetItem).filter_by(dataset_id=dataset_id)
    if split:
        q = q.filter(DatasetItem.split == split)
    items = q.order_by(DatasetItem.created_at).all()

    rows = [
        {
            "id": item.id,
            "dataset_id": item.dataset_id,
            "split": item.split,
            "input": item.input_data,
            "expected_output": item.expected_output,
            "tags": item.tags,
            "metadata": item.extra_metadata,
            "source_trace_id": item.source_trace_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]

    if format == "csv":
        return _csv_response(_as_csv(rows), f"dataset_{dataset_id}.csv")
    if format == "jsonl":
        content = "\n".join(json.dumps(r, default=str) for r in rows)
        return Response(
            content=content,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="dataset_{dataset_id}.jsonl"'},
        )
    return _json_response(rows, f"dataset_{dataset_id}.json")


# ---------------------------------------------------------------------------
# Experiment results export
# ---------------------------------------------------------------------------

@router.get("/experiments/{experiment_id}")
def export_experiment(
    experiment_id: str,
    format: str = Query("json", pattern="^(json|csv|jsonl)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export experiment results as JSON, JSONL, or CSV.
    Mirrors TraceIQ /v1/experiment/{experiment_id}/fetch.
    """
    exp = db.query(Experiment).filter_by(id=experiment_id).first()
    if not exp:
        raise HTTPException(404, detail="Experiment not found")

    results = db.query(ExperimentResult).filter_by(experiment_id=experiment_id).all()

    rows = [
        {
            "id": r.id,
            "experiment_id": r.experiment_id,
            "input": r.input_data,
            "output": r.actual_output,
            "expected": r.expected_output,
            "scores": r.scores,
            "overall_score": r.overall_score,
            "model": r.model,
            "latency_ms": r.latency_ms,
            "tokens_used": r.tokens_used,
            "cost_usd": float(r.cost_usd) if r.cost_usd else None,
            "error": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in results
    ]

    name = exp.name.replace(" ", "_")
    if format == "csv":
        return _csv_response(_as_csv(rows), f"experiment_{name}.csv")
    if format == "jsonl":
        content = "\n".join(json.dumps(r, default=str) for r in rows)
        return Response(
            content=content,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="experiment_{name}.jsonl"'},
        )
    return _json_response({"experiment": {"id": exp.id, "name": exp.name}, "results": rows}, f"experiment_{name}.json")
