"""
Datasets routes — full CRUD with versioning, items, and export.
"""



from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Dataset, DatasetItem, Trace, User

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DatasetCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    source: str = "manual"
    column_schema: Optional[List[Dict]] = None


class DatasetSchemaUpdate(BaseModel):
    column_schema: List[Dict]


class DatasetItemCreate(BaseModel):
    input_data: Optional[Any] = None
    expected_output: Optional[Any] = None
    metadata: Dict = {}
    tags: List[str] = []
    split: str = "all"
    source_trace_id: Optional[str] = None


class DatasetItemUpdate(BaseModel):
    expected_output: Optional[Any] = None
    metadata: Optional[Dict] = None
    tags: Optional[List[str]] = None
    split: Optional[str] = None


# ---------------------------------------------------------------------------
# Dataset endpoints
# ---------------------------------------------------------------------------

@router.post("/", status_code=201)
def create_dataset(
    payload: DatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = Dataset(
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        source=payload.source,
        version=1,
        example_count=0,
        column_schema=payload.column_schema,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return _dataset_dict(dataset)


@router.get("/")
def list_datasets(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasets = (
        db.query(Dataset)
        .filter_by(project_id=project_id, is_active=True)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    return [_dataset_dict(d) for d in datasets]


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = _get_or_404(db, dataset_id)
    return _dataset_dict(d)


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = _get_or_404(db, dataset_id)
    d.is_active = False
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Dataset items endpoints
# ---------------------------------------------------------------------------

@router.post("/{dataset_id}/items", status_code=201)
def add_item(
    dataset_id: str,
    payload: DatasetItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = _get_or_404(db, dataset_id)
    item = DatasetItem(
        dataset_id=dataset_id,
        project_id=d.project_id,
        input_data=payload.input_data,
        expected_output=payload.expected_output,
        extra_metadata=payload.metadata,
        tags=payload.tags,
        split=payload.split,
        source_trace_id=payload.source_trace_id,
    )
    db.add(item)
    d.example_count = (d.example_count or 0) + 1
    db.commit()
    db.refresh(item)
    return _item_dict(item)


@router.get("/{dataset_id}/items")
def list_items(
    dataset_id: str,
    split: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_or_404(db, dataset_id)
    q = db.query(DatasetItem).filter_by(dataset_id=dataset_id)
    if split:
        q = q.filter_by(split=split)
    items = q.order_by(DatasetItem.created_at).offset(offset).limit(limit).all()
    return [_item_dict(i) for i in items]


@router.patch("/{dataset_id}/items/{item_id}")
def update_item(
    dataset_id: str,
    item_id: str,
    payload: DatasetItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query(DatasetItem).filter_by(id=item_id, dataset_id=dataset_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    if payload.expected_output is not None:
        item.expected_output = payload.expected_output
    if payload.metadata is not None:
        item.extra_metadata = payload.metadata
    if payload.tags is not None:
        item.tags = payload.tags
    if payload.split is not None:
        item.split = payload.split
    db.commit()
    return _item_dict(item)


@router.delete("/{dataset_id}/items/{item_id}")
def delete_item(
    dataset_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query(DatasetItem).filter_by(id=item_id, dataset_id=dataset_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    d = _get_or_404(db, dataset_id)
    db.delete(item)
    d.example_count = max(0, (d.example_count or 1) - 1)
    db.commit()
    return {"deleted": True}


@router.post("/{dataset_id}/import-traces")
def import_from_traces(
    dataset_id: str,
    trace_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create dataset items from existing production traces."""
    d = _get_or_404(db, dataset_id)
    traces = db.query(Trace).filter(Trace.id.in_(trace_ids)).all()
    added = 0
    for trace in traces:
        item = DatasetItem(
            dataset_id=dataset_id,
            project_id=d.project_id,
            input_data=trace.input_data,
            expected_output=trace.expected_output,
            metadata={"source": "production_trace", "model": trace.model},
            source_trace_id=trace.id,
        )
        db.add(item)
        added += 1
    d.example_count = (d.example_count or 0) + added
    db.commit()
    return {"imported": added, "dataset_id": dataset_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, dataset_id: str) -> Dataset:
    d = db.query(Dataset).filter_by(id=dataset_id).first()
    if not d:
        raise HTTPException(404, "Dataset not found")
    return d


@router.patch("/{dataset_id}/schema")
def update_schema(
    dataset_id: str,
    payload: DatasetSchemaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the column schema for a dataset."""
    d = _get_or_404(db, dataset_id)
    d.column_schema = payload.column_schema
    db.commit()
    db.refresh(d)
    return _dataset_dict(d)


def _dataset_dict(d: Dataset) -> Dict:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "name": d.name,
        "description": d.description,
        "version": d.version,
        "source": d.source,
        "example_count": d.example_count,
        "column_schema": d.column_schema or [],
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _item_dict(i: DatasetItem) -> Dict:
    return {
        "id": i.id,
        "dataset_id": i.dataset_id,
        "input_data": i.input_data,
        "expected_output": i.expected_output,
        "metadata": i.extra_metadata,
        "tags": i.tags,
        "split": i.split,
        "source_trace_id": i.source_trace_id,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }
