"""
BTQL query routes — Phase 1 implementation.

POST /api/btql/query  — Execute a BTQL query
GET  /api/btql/schema — Get queryable columns per table
GET  /api/btql/history — List saved query history for current user
POST /api/btql/history — Save a query
DELETE /api/btql/history/{id} — Delete a saved query
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from backend.search.btql_engine import (
    QUERYABLE_COLUMNS,
    parse_btql,
    execute_btql,
)
from database.models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory query history per user session (simple implementation)
# A full implementation would use a DB table; this covers the MVP requirement.
# ---------------------------------------------------------------------------
_query_history: dict[str, list] = {}   # user_id -> [{id, query, created_at}]
_history_counter = 0


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BTQLRequest(BaseModel):
    query: str
    project_id: Optional[str] = None  # Scope results to a specific project


class BTQLResponse(BaseModel):
    table: str
    total: Optional[int]
    limit: int
    offset: int
    results: List[dict]
    columns: List[str]
    executed_at: str
    duration_ms: Optional[float]


class SavedQuery(BaseModel):
    name: str
    query: str
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/query", response_model=BTQLResponse)
def execute_query(
    payload: BTQLRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute a BTQL query and return results.

    Example queries:
      SELECT * FROM traces WHERE status = 'error' ORDER BY timestamp DESC LIMIT 50
      SELECT model, COUNT(*) as calls, AVG(latency_ms) as avg_lat FROM traces GROUP BY model
      SELECT * FROM traces WHERE environment = 'production' AND cost_usd > 0.01
    """
    import time
    start = time.perf_counter()

    try:
        btql = parse_btql(payload.query)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"BTQL parse error: {e}")

    try:
        result = execute_btql(db, btql, project_id_filter=payload.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"BTQL execution error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    duration_ms = (time.perf_counter() - start) * 1000

    return BTQLResponse(
        table=result["table"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        results=result["results"],
        columns=result["columns"],
        executed_at=datetime.utcnow().isoformat(),
        duration_ms=round(duration_ms, 2),
    )


@router.get("/schema")
def get_schema(
    table: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Return the queryable columns for each table (or a specific table)."""
    if table:
        if table not in QUERYABLE_COLUMNS:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown table '{table}'. Available: {list(QUERYABLE_COLUMNS)}"
            )
        return {"table": table, "columns": QUERYABLE_COLUMNS[table]}
    return {
        "tables": {
            tbl: list(cols.keys())
            for tbl, cols in QUERYABLE_COLUMNS.items()
        },
        "full_schema": QUERYABLE_COLUMNS,
    }


@router.get("/examples")
def get_example_queries(
    current_user: User = Depends(get_current_user),
):
    """Return example BTQL queries to help users get started."""
    return {
        "examples": [
            {
                "title": "All error traces",
                "query": "SELECT * FROM traces WHERE status = 'error' ORDER BY timestamp DESC LIMIT 50",
            },
            {
                "title": "Model usage summary",
                "query": "SELECT model, COUNT(*) as calls, AVG(latency_ms) as avg_lat, SUM(cost_usd) as total_cost FROM traces GROUP BY model",
            },
            {
                "title": "Production traces only",
                "query": "SELECT * FROM traces WHERE environment = 'production' ORDER BY timestamp DESC LIMIT 100",
            },
            {
                "title": "High cost traces",
                "query": "SELECT * FROM traces WHERE cost_usd > 0.05 ORDER BY cost_usd DESC LIMIT 25",
            },
            {
                "title": "Slow traces",
                "query": "SELECT * FROM traces WHERE latency_ms > 5000 ORDER BY latency_ms DESC LIMIT 25",
            },
            {
                "title": "Recent experiment scores",
                "query": "SELECT * FROM scores ORDER BY created_at DESC LIMIT 100",
            },
            {
                "title": "Token usage by model",
                "query": "SELECT model, SUM(total_tokens) as tokens, COUNT(*) as calls FROM traces GROUP BY model",
            },
            {
                "title": "Experiments with low scores",
                "query": "SELECT * FROM experiments WHERE avg_score < 0.5 ORDER BY avg_score ASC",
            },
        ]
    }


@router.get("/history")
def list_query_history(
    current_user: User = Depends(get_current_user),
):
    """List the current user's saved query history."""
    return _query_history.get(current_user.id, [])


@router.post("/history", status_code=201)
def save_query(
    payload: SavedQuery,
    current_user: User = Depends(get_current_user),
):
    """Save a query to the user's history."""
    global _history_counter
    _history_counter += 1
    entry = {
        "id": str(_history_counter),
        "name": payload.name,
        "query": payload.query,
        "description": payload.description,
        "created_at": datetime.utcnow().isoformat(),
    }
    _query_history.setdefault(current_user.id, []).insert(0, entry)
    # Keep at most 50 saved queries per user
    _query_history[current_user.id] = _query_history[current_user.id][:50]
    return entry


@router.delete("/history/{entry_id}", status_code=204)
def delete_saved_query(
    entry_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a saved query from history."""
    history = _query_history.get(current_user.id, [])
    _query_history[current_user.id] = [e for e in history if e["id"] != entry_id]
