"""
Evaluation routes - run evals and manage scorers.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any, Callable
from database.models import Eval, Project, Trace, Score, User, Dataset, DatasetItem
from backend.database import get_db
from backend.routes.auth import get_current_user
from backend.scoring import run_eval_task, score_single_trace
from datetime import datetime
import uuid
import types
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ScorerConfig(BaseModel):
    """Scorer configuration."""
    name: str
    type: str  # 'code', 'llm', 'expected'
    model: Optional[str] = None  # For LLM scorers
    config: Optional[dict] = None


class EvalCreate(BaseModel):
    """Create evaluation request."""
    name: str
    description: Optional[str] = None
    project_id: str
    dataset_id: Optional[str] = None  # If None, will run on single trace
    trace_id: Optional[str] = None  # If dataset_id is None, eval single trace
    scorers: List[ScorerConfig]
    task_config: Optional[dict] = None


class EvalResponse(BaseModel):
    """Evaluation response."""
    id: str
    name: str
    project_id: str
    status: str
    total_examples: int
    completed_examples: int
    avg_score: Optional[float] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class EvalDetailResponse(EvalResponse):
    """Detailed eval response with results."""
    description: Optional[str] = None
    results: Optional[Any] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@router.post("", response_model=EvalResponse, status_code=201)
async def create_eval(
    eval_create: EvalCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create and start an evaluation.
    Returns immediately with eval ID, runs asynchronously in background.
    """
    # Verify project access
    project = db.query(Project).filter(
        Project.id == eval_create.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to project"
        )
    
    # Determine examples to evaluate
    total_examples = 0
    if eval_create.dataset_id:
        dataset = db.query(Dataset).filter(Dataset.id == eval_create.dataset_id).first()
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        total_examples = dataset.example_count
    elif eval_create.trace_id:
        trace = db.query(Trace).filter(Trace.id == eval_create.trace_id).first()
        if not trace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trace not found"
            )
        total_examples = 1
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either dataset_id or trace_id must be provided"
        )
    
    # Create eval record
    eval_record = Eval(
        id=str(uuid.uuid4()),
        project_id=eval_create.project_id,
        dataset_id=eval_create.dataset_id,
        name=eval_create.name,
        description=eval_create.description,
        scorers=[s.dict() for s in eval_create.scorers],
        task_config=eval_create.task_config or {},
        status="pending",
        total_examples=total_examples,
        completed_examples=0
    )
    
    db.add(eval_record)
    db.commit()
    db.refresh(eval_record)
    
    # Schedule background task to run evaluation
    background_tasks.add_task(
        run_eval_task,
        eval_id=eval_record.id,
        project_id=eval_create.project_id,
        dataset_id=eval_create.dataset_id,
        trace_id=eval_create.trace_id,
        scorers=eval_create.scorers,
        db_url=str(db.bind.url)
    )
    
    logger.info(f"Created eval {eval_record.id} - running in background")
    
    return eval_record


@router.delete("/{eval_id}", status_code=204)
async def delete_eval(
    eval_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an evaluation."""
    eval_record = db.query(Eval).filter(Eval.id == eval_id).first()
    if not eval_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    project = db.query(Project).filter(
        Project.id == eval_record.project_id,
        Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    db.delete(eval_record)
    db.commit()


@router.get("/{eval_id}", response_model=EvalDetailResponse)
async def get_eval(
    eval_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get evaluation details."""
    eval_record = db.query(Eval).filter(Eval.id == eval_id).first()

    if not eval_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found"
        )

    # Verify user has access to project
    project = db.query(Project).filter(
        Project.id == eval_record.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return eval_record


@router.get("", response_model=List[EvalResponse])
async def list_evals(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List evaluations for a project."""
    # Verify project access
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to project"
        )
    
    evals = db.query(Eval).filter(
        Eval.project_id == project_id
    ).order_by(Eval.created_at.desc()).limit(limit).offset(offset).all()
    
    return evals


# ---------------------------------------------------------------------------
# Quick synchronous eval — single trace, real-time result for Playground
# ---------------------------------------------------------------------------

class QuickEvalRequest(BaseModel):
    """Request body for a quick synchronous LLM-as-judge evaluation."""
    trace_id: str
    metric_name: str
    model: str = "llama3"
    prompt_template: str


class QuickEvalResponse(BaseModel):
    """Immediate result from a quick eval."""
    trace_id: str
    metric_name: str
    model: str
    score: float
    explanation: str
    trace_input: object
    trace_output: object
    latency_ms: float


@router.post("/quick", response_model=QuickEvalResponse)
async def quick_eval(
    payload: QuickEvalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run a synchronous LLM-as-judge evaluation on a single trace via Ollama.
    Returns the score immediately — no background task, designed for the Playground.
    """
    trace = db.query(Trace).filter(Trace.id == payload.trace_id).first()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    # Verify user has access to the project that owns this trace
    project = db.query(Project).filter(
        Project.id == trace.project_id,
        Project.owner_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        result = await score_single_trace(
            trace=trace,
            metric_name=payload.metric_name,
            model=payload.model,
            prompt_template=payload.prompt_template,
        )
    except Exception as exc:
        logger.error(f"quick_eval failed for trace {payload.trace_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Ollama scorer failed: {exc}")

    return QuickEvalResponse(
        trace_id=payload.trace_id,
        metric_name=payload.metric_name,
        model=payload.model,
        score=result["score"],
        explanation=result["explanation"],
        trace_input=trace.input_data,
        trace_output=trace.output_data,
        latency_ms=result["latency_ms"],
    )


# ---------------------------------------------------------------------------
# Quick eval from a dataset item (uses expected_output as the "output" to judge)
# ---------------------------------------------------------------------------

class QuickEvalFromDatasetItemRequest(BaseModel):
    dataset_item_id: str
    metric_name: str
    model: str = "llama3"
    prompt_template: str


@router.post("/quick-dataset-item")
async def quick_eval_dataset_item(
    payload: QuickEvalFromDatasetItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run a synchronous LLM-as-judge evaluation on a dataset item.
    Uses item.input_data as {input} and item.expected_output as {output} in the prompt.
    """
    item = db.query(DatasetItem).filter(DatasetItem.id == payload.dataset_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dataset item not found")

    # Create a fake trace-like object so score_single_trace can consume it
    fake_trace = types.SimpleNamespace(
        input_data=item.input_data,
        output_data=item.expected_output,
    )

    try:
        result = await score_single_trace(
            trace=fake_trace,
            metric_name=payload.metric_name,
            model=payload.model,
            prompt_template=payload.prompt_template,
        )
    except Exception as exc:
        logger.error(f"quick_eval_dataset_item failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Scorer failed: {exc}")

    return {
        "dataset_item_id": payload.dataset_item_id,
        "metric_name": payload.metric_name,
        "model": payload.model,
        "score": result["score"],
        "explanation": result["explanation"],
        "trace_input": item.input_data,
        "trace_output": item.expected_output,
        "latency_ms": result["latency_ms"],
    }

