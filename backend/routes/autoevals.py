"""
Autoevals routes — run pre-built scorers via the API.
Mirrors TraceIQ: https://www.traciq.dev/docs/evaluate/autoevals
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.scoring import AUTOEVAL_REGISTRY, run_autoeval
from database.models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AutoevalRequest(BaseModel):
    scorer: str               # Name from AUTOEVAL_REGISTRY
    output: Any               # The model output to score
    expected: Optional[Any] = None   # Ground-truth / reference
    input_data: Optional[Any] = None # Original input (for context)
    config: Dict = {}         # Scorer-specific kwargs (e.g. pattern for regex, tolerance for numeric)


class BatchAutoevalRequest(BaseModel):
    scorer: str
    rows: List[Dict]          # Each: {output, expected?, input_data?}
    config: Dict = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def list_autoevals(current_user: User = Depends(get_current_user)):
    """List all available pre-built autoeval scorers."""
    descriptions = {
        "exact_match": "Exact string equality (case-insensitive by default)",
        "contains": "Checks whether expected value is contained in output",
        "regex": "Tests whether output matches a regex pattern (requires 'pattern' in config)",
        "json_validity": "Checks that output is valid parseable JSON",
        "levenshtein": "Normalised Levenshtein edit-distance similarity (0–1)",
        "word_overlap": "F1-based word token overlap (precision × recall harmonic mean)",
        "semantic_similarity": "Cosine similarity of sentence embeddings (requires sentence-transformers)",
        "numeric_diff": "Closeness of numeric values within a tolerance (config: tolerance=0.05)",
        "toxicity": "Keyword-based toxicity detection",
        "length": "Validates output length is within bounds (config: min_chars, max_chars)",
        "factuality": "LLM-as-judge: is output factually consistent with reference? (requires LLM key)",
        "summarization": "LLM-as-judge: is output a faithful, concise summary? (requires LLM key)",
    }
    return [
        {"name": name, "description": descriptions.get(name, "")}
        for name in AUTOEVAL_REGISTRY
    ]


@router.post("/run")
def run_single(
    req: AutoevalRequest,
    current_user: User = Depends(get_current_user),
):
    """Run a single autoeval scorer on one input/output pair."""
    result = run_autoeval(
        scorer_name=req.scorer,
        output=req.output,
        expected=req.expected,
        input_data=req.input_data,
        config=req.config,
    )
    return {"scorer": req.scorer, **result}


@router.post("/batch")
def run_batch(
    req: BatchAutoevalRequest,
    current_user: User = Depends(get_current_user),
):
    """Run an autoeval scorer across a batch of rows."""
    results = []
    for i, row in enumerate(req.rows):
        result = run_autoeval(
            scorer_name=req.scorer,
            output=row.get("output"),
            expected=row.get("expected"),
            input_data=row.get("input_data"),
            config=req.config,
        )
        results.append({"row": i, "scorer": req.scorer, **result})

    scores = [r["score"] for r in results]
    avg = sum(scores) / len(scores) if scores else 0.0
    return {
        "scorer": req.scorer,
        "count": len(results),
        "avg_score": round(avg, 4),
        "min_score": round(min(scores), 4) if scores else 0.0,
        "max_score": round(max(scores), 4) if scores else 0.0,
        "results": results,
    }
