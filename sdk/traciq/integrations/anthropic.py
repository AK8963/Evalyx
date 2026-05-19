"""
Anthropic auto-instrumentation — monkey-patches anthropic.Anthropic.messages.create
to automatically log every call as a TraceIQ trace.

Usage:
    from sdk.traciq.integrations.anthropic import patch_anthropic
    patch_anthropic(client=bt_client, project_id="my-project")
"""

import time
import logging
from functools import wraps
from typing import Optional

logger = logging.getLogger(__name__)


def patch_anthropic(client, project_id: str, trace_metadata: Optional[dict] = None) -> None:
    """
    Patch the anthropic module so that every Messages.create call is auto-traced.

    :param client:        TraceIQ SDK client
    :param project_id:    Target project ID
    :param trace_metadata: Extra metadata merged into every trace
    """
    try:
        import sdk.traciq.integrations.anthropic as _anthropic
    except ImportError:
        logger.warning("anthropic package not installed — skipping patch")
        return

    original_create = _anthropic.resources.messages.Messages.create

    @wraps(original_create)
    def _traced_create(self_inner, *args, **kwargs):
        start = time.perf_counter()
        error = None
        response = None
        try:
            response = original_create(self_inner, *args, **kwargs)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            model = kwargs.get("model", "unknown")
            messages = kwargs.get("messages", [])
            input_text = messages[-1].get("content", "") if messages else ""
            output_text = ""
            total_tokens = None
            if response is not None:
                try:
                    output_text = response.content[0].text if response.content else ""
                    usage = getattr(response, "usage", None)
                    if usage:
                        total_tokens = (getattr(usage, "input_tokens", 0) or 0) + (getattr(usage, "output_tokens", 0) or 0)
                except Exception:
                    pass

            meta = dict(trace_metadata or {})
            meta["provider"] = "anthropic"

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

    _anthropic.resources.messages.Messages.create = _traced_create
    logger.info("TraceIQ: anthropic.messages.create patched for auto-tracing")
