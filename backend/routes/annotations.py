"""
Annotations routes — human feedback, labels, and corrected outputs.
"""



from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Annotation, Label, Trace, User

router = APIRouter()


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

class LabelCreate(BaseModel):
    project_id: str
    name: str
    color: str = "#3B82F6"
    description: Optional[str] = None


@router.post("/labels", status_code=201)
def create_label(
    payload: LabelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    label = Label(**payload.dict())
    db.add(label)
    db.commit()
    db.refresh(label)
    return {"id": label.id, "name": label.name, "color": label.color}


@router.get("/labels")
def list_labels(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    labels = db.query(Label).filter_by(project_id=project_id).all()
    return [{"id": l.id, "name": l.name, "color": l.color, "description": l.description} for l in labels]


@router.delete("/labels/{label_id}")
def delete_label(
    label_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    label = db.query(Label).filter_by(id=label_id).first()
    if not label:
        raise HTTPException(404, "Label not found")
    db.delete(label)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

class AnnotationCreate(BaseModel):
    trace_id: str
    project_id: str
    thumbs_up: Optional[bool] = None
    rating: Optional[int] = None  # 1-5
    comment: Optional[str] = None
    label_ids: List[str] = []
    label_names: List[str] = []
    corrected_output: Optional[Any] = None
    annotation_type: str = "general"
    span_id: Optional[str] = None


class AnnotationUpdate(BaseModel):
    thumbs_up: Optional[bool] = None
    rating: Optional[int] = None
    comment: Optional[str] = None
    label_ids: Optional[List[str]] = None
    label_names: Optional[List[str]] = None
    corrected_output: Optional[Any] = None


@router.post("/", status_code=201)
def create_annotation(
    payload: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate trace exists
    trace = db.query(Trace).filter_by(id=payload.trace_id).first()
    if not trace:
        raise HTTPException(404, "Trace not found")

    ann = Annotation(
        trace_id=payload.trace_id,
        project_id=payload.project_id,
        user_id=current_user.id,
        thumbs_up=payload.thumbs_up,
        rating=payload.rating,
        comment=payload.comment,
        label_ids=payload.label_ids,
        label_names=payload.label_names,
        corrected_output=payload.corrected_output,
        annotation_type=payload.annotation_type,
        span_id=payload.span_id,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return _ann_dict(ann)


@router.get("/trace/{trace_id}")
def get_trace_annotations(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    anns = db.query(Annotation).filter_by(trace_id=trace_id).all()
    return [_ann_dict(a) for a in anns]


@router.get("/")
def list_annotations(
    project_id: str,
    annotation_type: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Annotation).filter_by(project_id=project_id)
    if annotation_type:
        q = q.filter_by(annotation_type=annotation_type)
    anns = q.order_by(Annotation.created_at.desc()).offset(offset).limit(limit).all()
    return [_ann_dict(a) for a in anns]


@router.patch("/{annotation_id}")
def update_annotation(
    annotation_id: str,
    payload: AnnotationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ann = db.query(Annotation).filter_by(id=annotation_id, user_id=current_user.id).first()
    if not ann:
        raise HTTPException(404, "Annotation not found")
    for field, val in payload.dict(exclude_none=True).items():
        setattr(ann, field, val)
    db.commit()
    return _ann_dict(ann)


@router.delete("/{annotation_id}")
def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ann = db.query(Annotation).filter_by(id=annotation_id, user_id=current_user.id).first()
    if not ann:
        raise HTTPException(404, "Annotation not found")
    db.delete(ann)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@router.get("/summary")
def annotation_summary(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func

    total = db.query(func.count(Annotation.id)).filter_by(project_id=project_id).scalar() or 0
    thumbs_up = (
        db.query(func.count(Annotation.id))
        .filter_by(project_id=project_id, thumbs_up=True)
        .scalar() or 0
    )
    thumbs_down = (
        db.query(func.count(Annotation.id))
        .filter_by(project_id=project_id, thumbs_up=False)
        .scalar() or 0
    )
    avg_rating = (
        db.query(func.avg(Annotation.rating))
        .filter(Annotation.project_id == project_id, Annotation.rating.isnot(None))
        .scalar()
    )
    return {
        "total": total,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "avg_rating": round(float(avg_rating), 2) if avg_rating else None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ann_dict(a: Annotation) -> Dict:
    return {
        "id": a.id,
        "trace_id": a.trace_id,
        "project_id": a.project_id,
        "user_id": a.user_id,
        "thumbs_up": a.thumbs_up,
        "rating": a.rating,
        "comment": a.comment,
        "label_ids": a.label_ids,
        "label_names": a.label_names,
        "corrected_output": a.corrected_output,
        "annotation_type": a.annotation_type,
        "span_id": a.span_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
