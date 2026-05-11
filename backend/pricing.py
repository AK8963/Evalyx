"""
Model pricing table and cost estimation.

Prices are in USD per 1,000 tokens (prompt / completion separately).
Sources: provider pricing pages, last updated May 2026.
Local / Ollama models are free ($0).

Usage:
    from backend.pricing import estimate_cost, get_all_models

    cost = estimate_cost("gpt-4o", prompt_tokens=500, completion_tokens=200)
    # → 0.00425
"""

from __future__ import annotations
from typing import Optional
import re

# ---------------------------------------------------------------------------
# Pricing table
# Each entry:  "canonical-model-name": (prompt_per_1k, completion_per_1k)
# ---------------------------------------------------------------------------
_PRICING: dict[str, tuple[float, float]] = {
    # ── OpenAI ───────────────────────────────────────────────────────────────
    "gpt-4o":                    (0.005,   0.015),
    "gpt-4o-mini":               (0.00015, 0.0006),
    "gpt-4-turbo":               (0.01,    0.03),
    "gpt-4-turbo-preview":       (0.01,    0.03),
    "gpt-4":                     (0.03,    0.06),
    "gpt-4-32k":                 (0.06,    0.12),
    "gpt-3.5-turbo":             (0.0005,  0.0015),
    "gpt-3.5-turbo-16k":         (0.001,   0.002),
    "o1":                        (0.015,   0.06),
    "o1-mini":                   (0.003,   0.012),
    "o3-mini":                   (0.0011,  0.0044),

    # ── Anthropic ────────────────────────────────────────────────────────────
    "claude-3-opus":             (0.015,   0.075),
    "claude-3-opus-20240229":    (0.015,   0.075),
    "claude-3-5-sonnet":         (0.003,   0.015),
    "claude-3-5-sonnet-20241022":(0.003,   0.015),
    "claude-3-sonnet":           (0.003,   0.015),
    "claude-3-sonnet-20240229":  (0.003,   0.015),
    "claude-3-haiku":            (0.00025, 0.00125),
    "claude-3-haiku-20240307":   (0.00025, 0.00125),
    "claude-3-5-haiku":          (0.0008,  0.004),
    "claude-opus-4":             (0.015,   0.075),
    "claude-sonnet-4":           (0.003,   0.015),

    # ── Google ───────────────────────────────────────────────────────────────
    "gemini-1.5-pro":            (0.00125, 0.005),
    "gemini-1.5-flash":          (0.000075,0.0003),
    "gemini-1.5-flash-8b":       (0.0000375,0.00015),
    "gemini-2.0-flash":          (0.0001,  0.0004),
    "gemini-pro":                (0.0005,  0.0015),
    "gemini-ultra":              (0.01,    0.03),

    # ── Meta / Llama (via API providers) ─────────────────────────────────────
    "llama-3.1-405b":            (0.003,   0.003),
    "llama-3.1-70b":             (0.00059, 0.00079),
    "llama-3.1-8b":              (0.0002,  0.0002),
    "llama-3-70b":               (0.00059, 0.00079),
    "llama-3-8b":                (0.0002,  0.0002),
    "llama-2-70b":               (0.00064, 0.00064),
    "llama-2-13b":               (0.00022, 0.00022),

    # ── Mistral ──────────────────────────────────────────────────────────────
    "mistral-large":             (0.004,   0.012),
    "mistral-large-2":           (0.003,   0.009),
    "mistral-medium":            (0.0027,  0.0081),
    "mistral-small":             (0.0002,  0.0006),
    "mistral-tiny":              (0.00014, 0.00042),
    "mixtral-8x7b":              (0.00024, 0.00024),
    "mixtral-8x22b":             (0.002,   0.006),

    # ── Cohere ───────────────────────────────────────────────────────────────
    "command-r-plus":            (0.003,   0.015),
    "command-r":                 (0.0005,  0.0015),
    "command":                   (0.001,   0.002),

    # ── Ollama / local — always free ──────────────────────────────────────────
    "ollama":                    (0.0, 0.0),
    "gemma2:2b":                 (0.0, 0.0),
    "gemma2:9b":                 (0.0, 0.0),
    "gemma2:27b":                (0.0, 0.0),
    "gemma:2b":                  (0.0, 0.0),
    "gemma:7b":                  (0.0, 0.0),
    "llama2":                    (0.0, 0.0),
    "llama3":                    (0.0, 0.0),
    "mistral":                   (0.0, 0.0),
    "neural-chat":               (0.0, 0.0),
    "phi3":                      (0.0, 0.0),
    "phi-3":                     (0.0, 0.0),
    "phi-3-mini":                (0.0, 0.0),
    "dolphin-mixtral":           (0.0, 0.0),
    "openchat":                  (0.0, 0.0),
    "starling-lm":               (0.0, 0.0),
    "vicuna":                    (0.0, 0.0),
    "orca-mini":                 (0.0, 0.0),
    "codellama":                 (0.0, 0.0),
    "deepseek-coder":            (0.0, 0.0),
    "deepseek-r1":               (0.0, 0.0),
    "qwen2":                     (0.0, 0.0),
    "nomic-embed-text":          (0.0, 0.0),
}

# Provider → canonical prefix (for fuzzy matching)
_PROVIDER_PREFIXES = {
    "gpt":      "openai",
    "o1":       "openai",
    "o3":       "openai",
    "claude":   "anthropic",
    "gemini":   "google",
    "llama":    "meta",
    "mistral":  "mistral",
    "mixtral":  "mistral",
    "command":  "cohere",
}


def _normalise(model: str) -> str:
    """Lower-case and strip common suffixes so fuzzy matching works."""
    return model.lower().strip()


def _lookup(model: str) -> Optional[tuple[float, float]]:
    """
    Return (prompt_per_1k, completion_per_1k) for a model name.
    Tries exact match first, then prefix/substring match.
    Returns None if not found.
    """
    key = _normalise(model)

    # 1. Exact match
    if key in _PRICING:
        return _PRICING[key]

    # 2. Prefix match (e.g. "gpt-4o-2024-11-20" → "gpt-4o")
    for canon, price in _PRICING.items():
        if key.startswith(canon) or canon.startswith(key):
            return price

    # 3. Local/Ollama heuristic — anything run locally is free
    ollama_keywords = {"ollama", "local", "localhost", ":11434"}
    if any(kw in key for kw in ollama_keywords):
        return (0.0, 0.0)

    # 4. Ollama tag format "model:tag" — if no pricing found, treat as local
    if re.match(r"^[a-z0-9._-]+:\w+$", key):
        return (0.0, 0.0)

    return None


def estimate_cost(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    custom_overrides: Optional[dict] = None,
) -> Optional[float]:
    """
    Estimate USD cost for a single LLM call.

    Args:
        model: Model name.
        prompt_tokens: Number of prompt/input tokens.
        completion_tokens: Number of completion/output tokens.
        total_tokens: Used when split is unknown (75/25 assumption).
        custom_overrides: Optional dict mapping model name →
            {"prompt_cost_per_1k": float, "completion_cost_per_1k": float, "is_free": bool}.
            These take precedence over the built-in table.

    Returns None if model is completely unrecognised.
    Returns 0.0 for known local/Ollama models.
    """
    if not model:
        return None

    # 1. Check custom overrides first
    if custom_overrides:
        key = _normalise(model)
        if key in custom_overrides:
            entry = custom_overrides[key]
            if entry.get("is_free"):
                return 0.0
            prompt_per_1k = entry.get("prompt_cost_per_1k", 0)
            completion_per_1k = entry.get("completion_cost_per_1k", 0)
            if not prompt_tokens and not completion_tokens and total_tokens:
                prompt_tokens = int(total_tokens * 0.75)
                completion_tokens = total_tokens - prompt_tokens
            cost = (prompt_tokens / 1000 * prompt_per_1k) + \
                   (completion_tokens / 1000 * completion_per_1k)
            return round(cost, 8)

    price = _lookup(model)
    if price is None:
        return None

    prompt_per_1k, completion_per_1k = price

    # Derive token counts if only total is known
    if not prompt_tokens and not completion_tokens and total_tokens:
        prompt_tokens = int(total_tokens * 0.75)
        completion_tokens = total_tokens - prompt_tokens

    cost = (prompt_tokens / 1000 * prompt_per_1k) + \
           (completion_tokens / 1000 * completion_per_1k)
    return round(cost, 8)


def get_model_info(model: str) -> Optional[dict]:
    """Return pricing info dict for a model, or None if unknown."""
    price = _lookup(model)
    if price is None:
        return None
    prompt_per_1k, completion_per_1k = price
    # Detect provider
    key = _normalise(model)
    provider = "unknown"
    for prefix, prov in _PROVIDER_PREFIXES.items():
        if key.startswith(prefix):
            provider = prov
            break
    if prompt_per_1k == 0.0 and completion_per_1k == 0.0:
        provider = "local"

    return {
        "model": model,
        "provider": provider,
        "prompt_cost_per_1k_tokens": prompt_per_1k,
        "completion_cost_per_1k_tokens": completion_per_1k,
        "is_free": prompt_per_1k == 0.0 and completion_per_1k == 0.0,
    }


def get_all_models() -> list[dict]:
    """Return pricing info for all known models."""
    seen = set()
    result = []
    for model in _PRICING:
        info = get_model_info(model)
        if info and model not in seen:
            seen.add(model)
            result.append(info)
    return result
