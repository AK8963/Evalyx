"""
Gateway routes — unified LLM routing with cost tracking, caching, and streaming.
"""



import asyncio
import hashlib
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import APIKeySetting, GatewayRequest, User, Trace

logger = logging.getLogger(__name__)
router = APIRouter()

# In-process response cache: {cache_key: response_dict}
_CACHE: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GatewayCompletionRequest(BaseModel):
    project_id: str
    model: str                  # 'openai/gpt-4', 'anthropic/claude-3-haiku', etc.
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 1024
    use_cache: bool = False
    fallback_models: List[str] = []
    # Reasoning model parameters
    thinking_budget: Optional[int] = None   # Anthropic: max thinking tokens
    reasoning_effort: Optional[str] = None  # OpenAI o-series: "low" | "medium" | "high"


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------

OPENAI_MODELS = {"gpt-4", "gpt-4o", "gpt-3.5-turbo", "gpt-4-turbo"}
ANTHROPIC_MODELS = {"claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
                    "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"}
GOOGLE_MODELS = {"gemini-pro", "gemini-1.5-pro", "gemini-flash"}

# Reasoning / thinking models that have special API requirements
OPENAI_REASONING_MODELS = {"o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"}
ANTHROPIC_THINKING_MODELS = {"claude-3-7-sonnet", "claude-3-7-sonnet-20250219"}


def _detect_provider(model: str) -> str:
    """Heuristically determine provider from model name."""
    m = model.lower()
    if "/" in m:
        return m.split("/")[0]
    if "claude" in m:
        return "anthropic"
    if "gemini" in m:
        return "google"
    if "ollama" in m or "llama" in m or "mistral" in m:
        return "ollama"
    return "openai"


def _resolve_key(db: Session, user: User, provider: str) -> Optional[str]:
    setting = db.query(APIKeySetting).filter_by(
        user_id=user.id, service=provider, is_active=True
    ).first()
    if setting:
        return setting.api_key
    try:
        from backend.config import settings as cfg
        key_map = {
            "openai": cfg.OPENAI_API_KEY,
            "anthropic": cfg.ANTHROPIC_API_KEY,
            "google": cfg.GOOGLE_API_KEY,
        }
        return key_map.get(provider)
    except Exception:
        return None


def _call_provider(
    provider: str,
    model: str,
    messages: List[Dict],
    temperature: float,
    max_tokens: int,
    api_key: Optional[str],
    thinking_budget: Optional[int] = None,
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    """Route to provider and return normalised response."""
    if provider == "openai":
        import openai
        if not api_key:
            raise HTTPException(400, "OpenAI API key not configured")
        client = openai.OpenAI(api_key=api_key)
        start = time.perf_counter()

        is_reasoning = model.lower() in OPENAI_REASONING_MODELS
        kwargs: Dict[str, Any] = {"model": model, "messages": messages}

        if is_reasoning:
            # o-series models: no temperature/top_p, use max_completion_tokens
            kwargs["max_completion_tokens"] = max_tokens
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
        else:
            kwargs["temperature"] = temperature
            kwargs["max_tokens"] = max_tokens

        resp = client.chat.completions.create(**kwargs)
        latency = (time.perf_counter() - start) * 1000
        usage = resp.usage

        result = {
            "content": resp.choices[0].message.content,
            "model": resp.model,
            "provider": "openai",
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "latency_ms": round(latency, 2),
            "is_reasoning_model": is_reasoning,
        }
        # Capture reasoning tokens if present (o-series)
        if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
            det = usage.completion_tokens_details
            reasoning_toks = getattr(det, "reasoning_tokens", None)
            if reasoning_toks:
                result["reasoning_tokens"] = reasoning_toks
        return result

    if provider == "anthropic":
        import anthropic
        if not api_key:
            raise HTTPException(400, "Anthropic API key not configured")
        client = anthropic.Anthropic(api_key=api_key)
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_msgs = [m for m in messages if m["role"] != "system"]
        start = time.perf_counter()

        is_thinking = model.lower() in ANTHROPIC_THINKING_MODELS or thinking_budget is not None
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system or "You are a helpful assistant.",
            "messages": user_msgs,
        }

        if is_thinking and thinking_budget:
            # Extended thinking mode — mutually exclusive with temperature
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        else:
            kwargs["temperature"] = temperature

        resp = client.messages.create(**kwargs)
        latency = (time.perf_counter() - start) * 1000

        # Extract text content and optional thinking content
        text_content = ""
        thinking_content = None
        for block in resp.content:
            if getattr(block, "type", None) == "thinking":
                thinking_content = getattr(block, "thinking", None)
            elif getattr(block, "type", None) == "text":
                text_content = block.text

        result = {
            "content": text_content,
            "model": model,
            "provider": "anthropic",
            "prompt_tokens": resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
            "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            "latency_ms": round(latency, 2),
            "is_reasoning_model": is_thinking,
        }
        if thinking_content:
            result["thinking_content"] = thinking_content
        # cache_creation_input_tokens present for extended thinking
        if hasattr(resp.usage, "cache_creation_input_tokens"):
            result["reasoning_tokens"] = getattr(resp.usage, "cache_creation_input_tokens", None)
        return result

    if provider == "ollama":
        import httpx
        from backend.config import settings as cfg
        # Strip the "ollama-" prefix and resolve short aliases to full tag names
        raw = model.replace("ollama-", "") if model.startswith("ollama-") else model
        _OLLAMA_ALIASES = {
            "llama3": "llama3:8b",
            "llama2": "llama2:latest",
            "mistral": "mistral:latest",
            "gemma2": "gemma2:9b",
            "gemma3": "gemma3:latest",
        }
        ollama_model = _OLLAMA_ALIASES.get(raw, raw)
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        start = time.perf_counter()
        resp = httpx.post(
            f"{cfg.OLLAMA_API_URL}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        latency = (time.perf_counter() - start) * 1000
        return {
            "content": data.get("response", ""),
            "model": model,
            "provider": "ollama",
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "latency_ms": round(latency, 2),
            "is_reasoning_model": False,
        }

    raise HTTPException(400, f"Unsupported provider: {provider}")


# ---------------------------------------------------------------------------
# Cost estimation (USD per 1K tokens — approximate rates)
# ---------------------------------------------------------------------------

_COST_TABLE: Dict[str, Dict[str, float]] = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
}


def _estimate_cost(model: str, prompt_tokens: Optional[int], completion_tokens: Optional[int]) -> Optional[float]:
    key = model.lower().replace("/", "-")
    rates = _COST_TABLE.get(key)
    if not rates or not prompt_tokens or not completion_tokens:
        return None
    return (prompt_tokens / 1000 * rates["input"]) + (completion_tokens / 1000 * rates["output"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/complete")
def gateway_complete(
    payload: GatewayCompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Route an LLM completion through the gateway with cost tracking."""
    # Cache check
    if payload.use_cache:
        ck = hashlib.sha256(
            json.dumps({"model": payload.model, "messages": payload.messages}, sort_keys=True).encode()
        ).hexdigest()
        if ck in _CACHE:
            cached = dict(_CACHE[ck])
            cached["cache_hit"] = True
            return cached

    provider = _detect_provider(payload.model)
    model_name = payload.model.split("/")[-1] if "/" in payload.model else payload.model
    api_key = _resolve_key(db, current_user, provider)

    # Try primary model, then fallbacks
    models_to_try = [payload.model] + payload.fallback_models
    result: Optional[Dict] = None
    last_error: Optional[str] = None

    for attempt_model in models_to_try:
        try:
            p = _detect_provider(attempt_model)
            k = _resolve_key(db, current_user, p)
            m = attempt_model.split("/")[-1] if "/" in attempt_model else attempt_model
            result = _call_provider(
                p, m, payload.messages, payload.temperature, payload.max_tokens, k,
                thinking_budget=payload.thinking_budget,
                reasoning_effort=payload.reasoning_effort,
            )
            break
        except HTTPException:
            raise
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Gateway attempt failed for %s: %s", attempt_model, exc)

    if result is None:
        raise HTTPException(502, f"All providers failed. Last error: {last_error}")

    # Cost estimation
    cost = _estimate_cost(result["model"], result.get("prompt_tokens"), result.get("completion_tokens"))
    result["cost_usd"] = cost
    result["cache_hit"] = False

    # Persist gateway request log
    try:
        req = GatewayRequest(
            project_id=payload.project_id,
            user_id=current_user.id,
            provider=result["provider"],
            model=result["model"],
            request_payload={"messages": payload.messages},
            response_payload={
                "content": result["content"],
                "thinking_content": result.get("thinking_content"),
                "reasoning_tokens": result.get("reasoning_tokens"),
                "is_reasoning_model": result.get("is_reasoning_model", False),
            },
            prompt_tokens=result.get("prompt_tokens"),
            completion_tokens=result.get("completion_tokens"),
            cost_usd=cost,
            latency_ms=result.get("latency_ms"),
            status_code=200,
        )
        db.add(req)

        # Also persist as a Trace so it appears in the Playground Eval tab selector
        user_messages = [m for m in payload.messages if m.get("role") == "user"]
        last_user_message = user_messages[-1]["content"] if user_messages else ""
        trace = Trace(
            id=str(__import__("uuid").uuid4()),
            project_id=payload.project_id,
            input_data={"question": last_user_message, "messages": payload.messages},
            output_data={"answer": result["content"]},
            model=result["model"],
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            total_tokens=result.get("total_tokens"),
            completion_tokens=result.get("completion_tokens"),
            prompt_tokens=result.get("prompt_tokens"),
            latency_ms=result.get("latency_ms"),
            cost_usd=cost,
            status="success",
            environment="playground",
            tags=["playground"],
        )
        db.add(trace)
        db.commit()
        result["trace_id"] = trace.id
    except Exception as exc:
        logger.warning("Failed to persist gateway request: %s", exc)
        result["trace_id"] = None

    # Store in cache
    if payload.use_cache:
        _CACHE[ck] = result

    return result


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------

class GatewayStreamRequest(BaseModel):
    project_id: str
    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 1024


async def _stream_openai(model: str, messages: List[Dict], temperature: float, max_tokens: int, api_key: str) -> AsyncGenerator[str, None]:
    import openai
    client = openai.AsyncOpenAI(api_key=api_key)
    start = time.perf_counter()
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    try:
        async with client.chat.completions.stream(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        ) as stream:
            async for event in stream:
                chunk = event.choices[0].delta.content if event.choices and event.choices[0].delta.content else ""
                if chunk:
                    yield f"data: {json.dumps({'token': chunk, 'done': False})}\n\n"
            final = await stream.get_final_completion()
            if final.usage:
                prompt_tokens = final.usage.prompt_tokens or 0
                completion_tokens = final.usage.completion_tokens or 0
                total_tokens = final.usage.total_tokens or 0
    except Exception as exc:
        yield f"data: {json.dumps({'error': str(exc), 'done': True})}\n\n"
        return
    latency = round((time.perf_counter() - start) * 1000, 2)
    cost = _estimate_cost(model, prompt_tokens, completion_tokens)
    yield f"data: {json.dumps({'token': '', 'done': True, 'total_tokens': total_tokens, 'latency_ms': latency, 'cost_usd': cost})}\n\n"


async def _stream_anthropic(model: str, messages: List[Dict], temperature: float, max_tokens: int, api_key: str) -> AsyncGenerator[str, None]:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    system = next((m["content"] for m in messages if m["role"] == "system"), "You are a helpful assistant.")
    user_msgs = [m for m in messages if m["role"] != "system"]
    start = time.perf_counter()
    input_tokens = 0
    output_tokens = 0
    try:
        async with client.messages.stream(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=user_msgs,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'token': text, 'done': False})}\n\n"
            final = await stream.get_final_message()
            input_tokens = final.usage.input_tokens or 0
            output_tokens = final.usage.output_tokens or 0
    except Exception as exc:
        yield f"data: {json.dumps({'error': str(exc), 'done': True})}\n\n"
        return
    latency = round((time.perf_counter() - start) * 1000, 2)
    total_tokens = input_tokens + output_tokens
    cost = _estimate_cost(model, input_tokens, output_tokens)
    yield f"data: {json.dumps({'token': '', 'done': True, 'total_tokens': total_tokens, 'latency_ms': latency, 'cost_usd': cost})}\n\n"


@router.post("/stream")
async def gateway_stream(
    payload: GatewayStreamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream LLM tokens via Server-Sent Events. Connect with EventSource or requests stream=True."""
    provider = _detect_provider(payload.model)
    model_name = payload.model.split("/")[-1] if "/" in payload.model else payload.model
    api_key = _resolve_key(db, current_user, provider)

    if provider == "openai":
        if not api_key:
            raise HTTPException(400, "OpenAI API key not configured")
        gen = _stream_openai(model_name, payload.messages, payload.temperature, payload.max_tokens, api_key)
    elif provider == "anthropic":
        if not api_key:
            raise HTTPException(400, "Anthropic API key not configured")
        gen = _stream_anthropic(model_name, payload.messages, payload.temperature, payload.max_tokens, api_key)
    else:
        # Non-streaming fallback for unsupported providers
        async def _fallback_gen():
            try:
                result = _call_provider(provider, model_name, payload.messages, payload.temperature, payload.max_tokens, api_key)
                content = result.get("content", "")
                # Simulate streaming by yielding words
                for word in content.split():
                    yield f"data: {json.dumps({'token': word + ' ', 'done': False})}\n\n"
                    await asyncio.sleep(0.01)
                yield f"data: {json.dumps({'token': '', 'done': True, 'total_tokens': result.get('total_tokens'), 'latency_ms': result.get('latency_ms'), 'cost_usd': result.get('cost_usd')})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': str(exc), 'done': True})}\n\n"
        gen = _fallback_gen()

    return StreamingResponse(gen, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/stats")
def gateway_stats(
    project_id: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cost and usage stats for gateway requests."""
    from datetime import timedelta
    from datetime import datetime
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            GatewayRequest.provider,
            GatewayRequest.model,
            func.count(GatewayRequest.id).label("requests"),
            func.avg(GatewayRequest.latency_ms).label("avg_latency"),
            func.sum(func.coalesce(GatewayRequest.cost_usd, 0)).label("total_cost"),
            func.sum(func.coalesce(GatewayRequest.prompt_tokens + GatewayRequest.completion_tokens, 0)).label("total_tokens"),
        )
        .filter(GatewayRequest.project_id == project_id, GatewayRequest.created_at >= since)
        .group_by(GatewayRequest.provider, GatewayRequest.model)
        .order_by(func.count(GatewayRequest.id).desc())
        .all()
    )

    return [
        {
            "provider": r.provider,
            "model": r.model,
            "requests": r.requests,
            "avg_latency_ms": round(float(r.avg_latency), 2) if r.avg_latency else None,
            "total_cost_usd": round(float(r.total_cost), 6),
            "total_tokens": int(r.total_tokens) if r.total_tokens else 0,
        }
        for r in rows
    ]


@router.get("/providers")
def list_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List configured providers for the current user."""
    settings = db.query(APIKeySetting).filter_by(user_id=current_user.id, is_active=True).all()
    return [{"service": s.service, "model": s.model} for s in settings]


@router.get("/models")
def list_ollama_models(
    current_user: User = Depends(get_current_user),
):
    """List models available in the local Ollama instance."""
    import requests as _req
    from backend.config import settings as _settings
    try:
        resp = _req.get(f"{_settings.OLLAMA_API_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return {"models": models, "available": True}
    except Exception as exc:
        logger.warning("Could not reach Ollama: %s", exc)
        return {"models": [], "available": False, "error": str(exc)}
