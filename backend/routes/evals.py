"""
Evaluation routes - run evals and manage scorers.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any, Callable
from database.models import Eval, Project, Trace, Score, User, Dataset
from backend.database import get_db
from backend.routes.auth import get_current_user
from backend.scoring import run_eval_task
from datetime import datetime
import uuid
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
    results: Optional[dict] = None
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
