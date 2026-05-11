"""
Playgrounds routes — real-time LLM prompt iteration with scoring.
"""



import json
import time
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import APIKeySetting, User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PlaygroundRun(BaseModel):
    project_id: str
    system_prompt: Optional[str] = None
    user_message: str
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1024
    # Optional scorer to run against output
    scorer_type: Optional[str] = None  # 'expected', 'llm'
    expected_output: Optional[str] = None
    scorer_model: Optional[str] = None


class PlaygroundBatchRun(BaseModel):
    """Run the same config against multiple inputs."""
    project_id: str
    system_prompt: Optional[str] = None
    inputs: List[str]
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1024


# ---------------------------------------------------------------------------
# LLM runner helpers
# ---------------------------------------------------------------------------

def _resolve_api_key(db: Session, user: User, service: str) -> Optional[str]:
    setting = (
        db.query(APIKeySetting)
        .filter_by(user_id=user.id, service=service, is_active=True)
        .first()
    )
    if setting:
        return setting.api_key
    try:
        from backend.config import settings as cfg
        return getattr(cfg, f"{service.upper()}_API_KEY", None)
    except Exception:
        return None


def _call_openai(
    system: Optional[str],
    user_msg: str,
    model: str,
    temperature: float,
    max_tokens: int,
    api_key: str,
) -> Dict[str, Any]:
    import openai

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_msg})

    start = time.perf_counter()
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    output = resp.choices[0].message.content
    usage = resp.usage
    return {
        "output": output,
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "model": model,
    }


def _call_anthropic(
    system: Optional[str],
    user_msg: str,
    model: str,
    temperature: float,
    max_tokens: int,
    api_key: str,
) -> Dict[str, Any]:
    import anthropic

    start = time.perf_counter()
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system or "You are a helpful assistant.",
        messages=[{"role": "user", "content": user_msg}],
    )
    latency_ms = (time.perf_counter() - start) * 1000
    return {
        "output": resp.content[0].text,
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": resp.usage.input_tokens,
        "completion_tokens": resp.usage.output_tokens,
        "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
        "model": model,
    }


def _call_ollama(
    system: Optional[str],
    user_msg: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, Any]:
    import httpx
    from backend.config import settings as cfg

    prompt = f"{system}\n\n{user_msg}" if system else user_msg
    start = time.perf_counter()
    resp = httpx.post(
        f"{cfg.OLLAMA_API_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    latency_ms = (time.perf_counter() - start) * 1000
    return {
        "output": data.get("response", ""),
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "model": model,
    }


def _run_llm(db: Session, user: User, payload: PlaygroundRun) -> Dict[str, Any]:
    """Route to the appropriate LLM provider."""
    model_lower = payload.model.lower()

    if "claude" in model_lower:
        key = _resolve_api_key(db, user, "anthropic")
        if not key:
            raise HTTPException(400, "Anthropic API key not configured")
        return _call_anthropic(payload.system_prompt, payload.user_message, payload.model, payload.temperature, payload.max_tokens, key)

    if "ollama" in model_lower or "/" in model_lower:
        return _call_ollama(payload.system_prompt, payload.user_message, payload.model, payload.temperature, payload.max_tokens)

    # Default: OpenAI
    key = _resolve_api_key(db, user, "openai")
    if not key:
        raise HTTPException(400, "OpenAI API key not configured")
    return _call_openai(payload.system_prompt, payload.user_message, payload.model, payload.temperature, payload.max_tokens, key)


# ---------------------------------------------------------------------------
# Scorer helper
# ---------------------------------------------------------------------------

def _score_output(output: str, expected: Optional[str], scorer_type: Optional[str]) -> Optional[Dict]:
    if not scorer_type or not expected:
        return None
    if scorer_type == "expected":
        exact = output.strip() == expected.strip()
        contains = expected.lower() in output.lower()
        return {
            "scorer": "expected_value",
            "exact_match": exact,
            "contains_match": contains,
            "score": 1.0 if exact else (0.5 if contains else 0.0),
        }
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run")
def run_playground(
    payload: PlaygroundRun,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a single playground run and return output + metrics."""
    try:
        result = _run_llm(db, current_user, payload)
        score = _score_output(
            result.get("output", ""),
            payload.expected_output,
            payload.scorer_type,
        )
        result["score"] = score
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Playground run failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"LLM call failed: {exc}")


@router.post("/batch")
def run_playground_batch(
    payload: PlaygroundBatchRun,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run same config against multiple inputs (for quick dataset sweeps)."""
    results = []
    for user_msg in payload.inputs:
        single = PlaygroundRun(
            project_id=payload.project_id,
            system_prompt=payload.system_prompt,
            user_message=user_msg,
            model=payload.model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
        try:
            r = _run_llm(db, current_user, single)
            r["input"] = user_msg
            r["error"] = None
        except Exception as exc:
            r = {"input": user_msg, "output": None, "error": str(exc)}
        results.append(r)
    return {"results": results, "total": len(results)}
