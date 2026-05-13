"""
Trace routes - ingestion and retrieval of LLM traces.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime, timedelta
from database.models import Trace, Project, User, Score, ModelPricing, MaskingRule
from backend.database import get_db
from backend.routes.auth import get_current_user
from backend.pricing import estimate_cost
from backend.routes.masking import apply_masking_rules
import uuid
import json

router = APIRouter()


class TraceInput(BaseModel):
    """Trace input model - what SDK sends.
    
    Provide EITHER project_id (UUID) OR project_name (human-readable).
    """
    project_id: Optional[str] = None
    project_name: Optional[str] = None  # convenience: looked up by name
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    expected_output: Optional[Any] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    status: str = "success"
    error_message: Optional[str] = None
    spans: Optional[List[Any]] = None
    metadata: Optional[dict] = None
    tags: Optional[List[str]] = None
    timestamp: Optional[datetime] = None
    environment: Optional[str] = "production"  # dev, staging, production


class TraceResponse(BaseModel):
    """Trace response model."""
    id: str
    project_id: str
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    model: Optional[str] = None
    status: str
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    timestamp: datetime
    tags: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class TraceDetailResponse(TraceResponse):
    """Detailed trace response with scores."""
    expected_output: Optional[Any] = None
    total_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    spans: Optional[List[Any]] = None
    metadata: Optional[dict] = None   # maps from trace.meta column (avoids SQLAlchemy MetaData)
    scores: Optional[List[dict]] = None
    error_message: Optional[str] = None
    environment: Optional[str] = None
    created_at: datetime


def _cost_for_ingest(trace_input: "TraceInput", user_id: str, db: "Session") -> Optional[float]:
    """Load user's custom pricing and estimate cost for a single trace."""
    custom_rows = db.query(ModelPricing).filter(ModelPricing.user_id == user_id).all()
    custom_overrides = {
        r.model.lower(): {
            "prompt_cost_per_1k": float(r.prompt_cost_per_1k),
            "completion_cost_per_1k": float(r.completion_cost_per_1k),
            "is_free": r.is_free,
        }
        for r in custom_rows
    }
    return estimate_cost(
        trace_input.model or "",
        prompt_tokens=trace_input.prompt_tokens or 0,
        completion_tokens=trace_input.completion_tokens or 0,
        total_tokens=trace_input.total_tokens or 0,
        custom_overrides=custom_overrides or None,
    )


@router.post("/batch", status_code=201)
async def ingest_traces(
    traces: List[TraceInput],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ingest batch of traces from SDK.
    This is the main endpoint for trace collection.
    """
    if not traces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No traces provided"
        )

    # Resolve project_name → project_id for any trace that needs it
    name_cache: dict = {}
    for t in traces:
        if not t.project_id:
            if not t.project_name:
                raise HTTPException(status_code=400, detail="Each trace needs project_id or project_name")
            if t.project_name not in name_cache:
                p = db.query(Project).filter(
                    Project.name == t.project_name,
                    Project.owner_id == current_user.id,
                ).first()
                if not p:
                    raise HTTPException(status_code=404, detail=f"Project '{t.project_name}' not found")
                name_cache[t.project_name] = str(p.id)
            t.project_id = name_cache[t.project_name]

    # Validate all traces belong to user's projects
    project_ids = {t.project_id for t in traces}
    user_projects = db.query(Project).filter(
        Project.owner_id == current_user.id,
        Project.id.in_(project_ids)
    ).all()

    user_project_ids = {p.id for p in user_projects}
    for project_id in project_ids:
        if project_id not in user_project_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to project {project_id}"
            )

    # Load custom pricing overrides for this user (single DB query)
    custom_rows = db.query(ModelPricing).filter(ModelPricing.user_id == current_user.id).all()
    custom_overrides = {
        r.model.lower(): {
            "prompt_cost_per_1k": float(r.prompt_cost_per_1k),
            "completion_cost_per_1k": float(r.completion_cost_per_1k),
            "is_free": r.is_free,
        }
        for r in custom_rows
    }

    # Create trace records
    created_traces = []
    for trace_input in traces:
        # Auto-calculate cost if not provided by the client
        cost = trace_input.cost_usd
        if cost is None and trace_input.model:
            cost = estimate_cost(
                trace_input.model,
                prompt_tokens=trace_input.prompt_tokens or 0,
                completion_tokens=trace_input.completion_tokens or 0,
                total_tokens=trace_input.total_tokens or 0,
                custom_overrides=custom_overrides or None,
            )

        # Apply data masking rules before storage
        masking_rules = db.query(MaskingRule).filter_by(
            project_id=trace_input.project_id, is_active=True
        ).all()
        masked_input = apply_masking_rules(trace_input.input_data, masking_rules)
        masked_output = apply_masking_rules(trace_input.output_data, masking_rules)

        trace = Trace(
            id=str(uuid.uuid4()),
            project_id=trace_input.project_id,
            input_data=masked_input,
            output_data=masked_output,
            expected_output=trace_input.expected_output,
            model=trace_input.model,
            temperature=trace_input.temperature,
            max_tokens=trace_input.max_tokens,
            total_tokens=trace_input.total_tokens,
            completion_tokens=trace_input.completion_tokens,
            prompt_tokens=trace_input.prompt_tokens,
            cost_usd=cost,
            latency_ms=trace_input.latency_ms,
            status=trace_input.status,
            error_message=trace_input.error_message,
            spans=trace_input.spans or [],
            meta=trace_input.metadata or {},
            tags=trace_input.tags or [],
            environment=trace_input.environment or "production",
            timestamp=trace_input.timestamp or datetime.utcnow()
        )
        db.add(trace)
        created_traces.append(trace)
    
    db.commit()
    
    # Refresh to get IDs
    for trace in created_traces:
        db.refresh(trace)
    
    return {
        "status": "success",
        "count": len(created_traces),
        "trace_ids": [t.id for t in created_traces]
    }


@router.post("", response_model=TraceResponse, status_code=201)
async def create_trace(
    trace_input: TraceInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a single trace."""
    result = await ingest_traces([trace_input], current_user, db)
    trace_id = result["trace_ids"][0]
    return db.query(Trace).filter(Trace.id == trace_id).first()


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(
    trace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trace details with all scores."""
    
    trace = db.query(Trace).filter(Trace.id == trace_id).first()
    
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found"
        )

    # Verify user has access to this project
    project = db.query(Project).filter(
        Project.id == trace.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get associated scores
    scores = db.query(Score).filter(Score.trace_id == trace_id).all()
    scores_data = [
        {
            "id": s.id,
            "scorer_name": s.scorer_name,
            "scorer_type": s.scorer_type,
            "score_value": s.score_value,
            "explanation": s.explanation
        }
        for s in scores
    ]
    
    response = TraceDetailResponse(
        id=trace.id,
        project_id=trace.project_id,
        input_data=trace.input_data,
        output_data=trace.output_data,
        expected_output=trace.expected_output,
        model=trace.model,
        status=trace.status,
        latency_ms=trace.latency_ms,
        cost_usd=trace.cost_usd,
        total_tokens=trace.total_tokens,
        completion_tokens=trace.completion_tokens,
        prompt_tokens=trace.prompt_tokens,
        error_message=trace.error_message,
        environment=getattr(trace, 'environment', None),
        tags=trace.tags,
        spans=trace.spans,
        metadata=trace.meta or {},
        scores=scores_data,
        timestamp=trace.timestamp,
        created_at=trace.created_at,
    )
    
    return response


@router.get("", response_model=List[TraceResponse])
async def list_traces(
    project_id: str,
    model: Optional[str] = None,
    status_filter: Optional[str] = None,
    environment: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List traces with filters."""
    # Verify user has access to project
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to project"
        )
    
    # Build query
    query = db.query(Trace).filter(Trace.project_id == project_id)
    
    if model:
        query = query.filter(Trace.model == model)
    
    if status_filter:
        query = query.filter(Trace.status == status_filter)

    if environment:
        query = query.filter(Trace.environment == environment)
    
    # Get total count
    total = query.count()
    
    # Get paginated results, ordered by timestamp descending
    traces = query.order_by(desc(Trace.timestamp)).limit(limit).offset(offset).all()
    
    return traces


@router.delete("/{trace_id}", status_code=204)
async def delete_trace(
    trace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a trace."""
    trace = db.query(Trace).filter(Trace.id == trace_id).first()

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found"
        )

    # Verify user has access
    project = db.query(Project).filter(
        Project.id == trace.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    db.delete(trace)
    db.commit()
    
    return None


# ---------------------------------------------------------------------------
# /ingest  — SDK-friendly single-trace endpoint (also accepts project_name)
# ---------------------------------------------------------------------------

@router.post("/ingest", status_code=201, tags=["sdk"])
async def ingest_single_trace(
    trace_input: TraceInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingest a **single trace** from any external application.

    Accepts **X-API-Key** header or **Authorization: Bearer <api_key>** for
    SDK / programmatic use (no browser login required).

    You may pass either:
    - ``project_id`` — the project UUID visible in the dashboard URL
    - ``project_name`` — the human-readable project name (case-sensitive)

    Example with curl::

        curl -X POST http://localhost:8000/api/traces/ingest \\
             -H "X-API-Key: traciq_xxxx" \\
             -H "Content-Type: application/json" \\
             -d '{
               "project_name": "my-project",
               "model": "gpt-4",
               "input_data": {"prompt": "Hello"},
               "output_data": {"response": "Hi!"},
               "latency_ms": 320,
               "total_tokens": 42
             }'
    """
    # Resolve project by name if UUID not provided
    if not trace_input.project_id:
        if not trace_input.project_name:
            raise HTTPException(
                status_code=400,
                detail="Provide either project_id or project_name",
            )
        project = db.query(Project).filter(
            Project.name == trace_input.project_name,
            Project.owner_id == current_user.id,
        ).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{trace_input.project_name}' not found",
            )
        trace_input.project_id = str(project.id)
    else:
        project = db.query(Project).filter(
            Project.id == trace_input.project_id,
            Project.owner_id == current_user.id,
        ).first()
        if not project:
            raise HTTPException(status_code=403, detail="Access denied to project")

    trace = Trace(
        id=str(uuid.uuid4()),
        project_id=trace_input.project_id,
        input_data=trace_input.input_data,
        output_data=trace_input.output_data,
        expected_output=trace_input.expected_output,
        model=trace_input.model,
        temperature=trace_input.temperature,
        max_tokens=trace_input.max_tokens,
        total_tokens=trace_input.total_tokens,
        completion_tokens=trace_input.completion_tokens,
        prompt_tokens=trace_input.prompt_tokens,
        cost_usd=trace_input.cost_usd if trace_input.cost_usd is not None else _cost_for_ingest(
            trace_input, current_user.id, db
        ),
        latency_ms=trace_input.latency_ms,
        status=trace_input.status,
        error_message=trace_input.error_message,
        spans=trace_input.spans,
        meta=trace_input.metadata,
        tags=trace_input.tags,
        timestamp=trace_input.timestamp or datetime.utcnow(),
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return {"id": trace.id, "project_id": trace.project_id, "status": "accepted"}
