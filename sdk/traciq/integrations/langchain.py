"""
LangChain callback handler — automatically traces every LLM call made
through a LangChain chain or agent.

Usage:
    from sdk.traciq.integrations.langchain import TraceIQCallbackHandler
    handler = TraceIQCallbackHandler(client=bt_client, project_id="my-project")
    chain.invoke({"input": "..."}, config={"callbacks": [handler]})
"""

import time
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    _LC_AVAILABLE = True
except ImportError:
    try:
        from langchain.callbacks.base import BaseCallbackHandler
        _LC_AVAILABLE = True
    except ImportError:
        _LC_AVAILABLE = False
        BaseCallbackHandler = object  # type: ignore


class TraceIQCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    """LangChain callback handler that logs LLM calls to TraceIQ."""

    def __init__(self, client, project_id: str, trace_metadata: Optional[dict] = None):
        if not _LC_AVAILABLE:
            raise ImportError("langchain or langchain-core is required for this integration")
        super().__init__()
        self._client = client
        self._project_id = project_id
        self._trace_metadata = trace_metadata or {}
        self._starts: Dict[str, float] = {}

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._starts[str(run_id)] = time.perf_counter()

    def on_llm_end(self, response, *, run_id: UUID, **kwargs: Any) -> None:
        start = self._starts.pop(str(run_id), None)
        latency_ms = (time.perf_counter() - start) * 1000 if start else 0

        output_text = ""
        total_tokens = None
        model = "langchain"
        try:
            gen = response.generations[0][0]
            output_text = gen.text
            if hasattr(gen, "message") and hasattr(gen.message, "response_metadata"):
                meta = gen.message.response_metadata
                model = meta.get("model_name", model)
            if response.llm_output:
                token_usage = response.llm_output.get("token_usage", {})
                total_tokens = token_usage.get("total_tokens")
        except Exception:
            pass

        meta = dict(self._trace_metadata)
        meta["provider"] = "langchain"

        try:
            self._client.log(
                project_id=self._project_id,
                input="(langchain chain)",
                output=output_text,
                model=model,
                latency_ms=latency_ms,
                total_tokens=total_tokens,
                status="success",
                metadata=meta,
            )
        except Exception as e:
            logger.warning(f"TraceIQ LangChain callback error: {e}")

    def on_llm_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        start = self._starts.pop(str(run_id), None)
        latency_ms = (time.perf_counter() - start) * 1000 if start else 0
        meta = dict(self._trace_metadata)
        meta["provider"] = "langchain"
        try:
            self._client.log(
                project_id=self._project_id,
                input="(langchain chain)",
                output="",
                model="langchain",
                latency_ms=latency_ms,
                status="error",
                metadata=meta,
                error=str(error),
            )
        except Exception as e:
            logger.warning(f"TraceIQ LangChain callback error: {e}")
