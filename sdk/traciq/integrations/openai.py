"""
OpenAI auto-instrumentation — monkey-patches openai.chat.completions.create
to automatically log every call as a TraceIQ trace.

Usage:
    from sdk.traciq.integrations.openai import patch_openai
    patch_openai(client=bt_client, project_id="my-project")
"""

import time
import logging
from functools import wraps
from typing import Optional

logger = logging.getLogger(__name__)


def patch_openai(client, project_id: str, trace_metadata: Optional[dict] = None) -> None:
    """
    Patch the openai module so that every ChatCompletion call is auto-traced.

    :param client:        TraceIQ SDK client (sdk.traciq.client.TraceIQClient)
    :param project_id:    Target project ID for the traces
    :param trace_metadata: Extra metadata merged into every trace
    """
    try:
        import sdk.traciq.integrations.openai as _openai
    except ImportError:
        logger.warning("openai package not installed — skipping patch")
        return

    # Support both openai v1 (client-based) and older chat.completions.create
    try:
        original_create = _openai.chat.completions.create
    except AttributeError:
        logger.warning("openai.chat.completions.create not found — skipping patch")
        return

    @wraps(original_create)
    def _traced_create(*args, **kwargs):
        start = time.perf_counter()
        error = None
        response = None
        try:
            response = original_create(*args, **kwargs)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            model = kwargs.get("model", "unknown")
            messages = kwargs.get("messages", [])
            input_text = messages[-1]["content"] if messages else ""
            output_text = ""
            total_tokens = None
            if response is not None:
                try:
                    output_text = response.choices[0].message.content or ""
                    total_tokens = response.usage.total_tokens if response.usage else None
                except Exception:
                    pass

            meta = dict(trace_metadata or {})
            meta["provider"] = "openai"

            try:
                client.log(
                    project_id=project_id,
                    input=input_text,
                    output=output_text,
                    model=model,
                    latency_ms=latency_ms,
                    total_tokens=total_tokens,
                    status="error" if error else "success",
                    metadata=meta,
                    error=error,
                )
            except Exception as log_exc:
                logger.warning(f"TraceIQ auto-trace failed: {log_exc}")

    _openai.chat.completions.create = _traced_create
    logger.info("TraceIQ: openai.chat.completions.create patched for auto-tracing")
