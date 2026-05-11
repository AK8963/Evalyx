"""
LangGraph integration — automatically trace LangGraph StateGraph executions.

Usage:
    from sdk.traciq.integrations.langgraph import TraceIQLangGraphTracer, add_tracing

    # Option 1 — wrap the entire graph.invoke() call:
    from sdk.traciq.integrations.langgraph import trace_graph

    result = trace_graph(
        graph=compiled_graph,
        inputs={"messages": [...]},
        client=bt_client,
        project_id="proj-123",
    )

    # Option 2 — add a tracing node to the graph:
    graph = add_tracing(graph, client=bt_client, project_id="proj-123")

    # Option 3 — use the LangChain callback (LangGraph uses LangChain callbacks):
    from sdk.traciq.integrations.langchain import TraceIQCallbackHandler
    compiled.invoke(inputs, config={"callbacks": [TraceIQCallbackHandler(client, project_id)]})
"""

import functools
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def trace_graph(
    graph,
    inputs: Dict,
    client,
    project_id: str,
    name: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Any:
    """
    Invoke a compiled LangGraph StateGraph and trace the full run.

    Args:
        graph: A compiled LangGraph graph (result of graph.compile()).
        inputs: The input dict to pass to graph.invoke().
        client: TraceIQ client instance.
        project_id: The project to log the trace to.
        name: Optional trace name (defaults to "langgraph").
        metadata: Extra metadata to attach to the trace.

    Returns:
        The graph's output (same as graph.invoke(inputs)).
    """
    trace_name = name or "langgraph"
    start = time.perf_counter()
    error = None
    result = None

    try:
        result = graph.invoke(inputs)
        return result
    except Exception as e:
        error = e
        raise
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        try:
            # Serialise inputs/outputs safely
            safe_input = _safe_serialise(inputs)
            safe_output = _safe_serialise(result) if result is not None else None
            client.trace(
                project_id=project_id,
                input_data=safe_input,
                output_data=safe_output,
                model=f"langgraph/{trace_name}",
                latency_ms=round(latency_ms, 2),
                status="error" if error else "success",
                error_message=str(error) if error else None,
                meta={
                    "framework": "langgraph",
                    "trace_name": trace_name,
                    **(metadata or {}),
                },
            )
        except Exception as trace_err:
            logger.warning(f"[TraceIQ] Failed to record LangGraph trace: {trace_err}")


def trace_graph_stream(
    graph,
    inputs: Dict,
    client,
    project_id: str,
    name: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """
    Stream a compiled LangGraph StateGraph and trace each emitted chunk.

    Yields each chunk from graph.stream() and records a trace at the end.
    """
    trace_name = name or "langgraph_stream"
    start = time.perf_counter()
    chunks = []
    error = None

    try:
        for chunk in graph.stream(inputs):
            chunks.append(chunk)
            yield chunk
    except Exception as e:
        error = e
        raise
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        try:
            client.trace(
                project_id=project_id,
                input_data=_safe_serialise(inputs),
                output_data={"chunks": len(chunks), "last_chunk": _safe_serialise(chunks[-1]) if chunks else None},
                model=f"langgraph/{trace_name}",
                latency_ms=round(latency_ms, 2),
                status="error" if error else "success",
                error_message=str(error) if error else None,
                meta={
                    "framework": "langgraph",
                    "trace_name": trace_name,
                    "stream": True,
                    **(metadata or {}),
                },
            )
        except Exception as trace_err:
            logger.warning(f"[TraceIQ] Failed to record LangGraph stream trace: {trace_err}")


class TraceIQLangGraphTracer:
    """
    Context manager / decorator that traces a LangGraph graph invocation.

    Example:
        with TraceIQLangGraphTracer(client, project_id, "my_graph") as tracer:
            result = compiled_graph.invoke(inputs)
            tracer.set_output(result)
    """

    def __init__(
        self,
        client,
        project_id: str,
        name: str = "langgraph",
        metadata: Optional[dict] = None,
    ):
        self._client = client
        self._project_id = project_id
        self._name = name
        self._metadata = metadata or {}
        self._start = None
        self._input = None
        self._output = None
        self._error = None

    def set_input(self, data: Any) -> "TraceIQLangGraphTracer":
        self._input = data
        return self

    def set_output(self, data: Any) -> "TraceIQLangGraphTracer":
        self._output = data
        return self

    def __enter__(self) -> "TraceIQLangGraphTracer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        latency_ms = (time.perf_counter() - self._start) * 1000 if self._start else 0
        self._error = exc_val
        try:
            self._client.trace(
                project_id=self._project_id,
                input_data=_safe_serialise(self._input),
                output_data=_safe_serialise(self._output),
                model=f"langgraph/{self._name}",
                latency_ms=round(latency_ms, 2),
                status="error" if self._error else "success",
                error_message=str(self._error) if self._error else None,
                meta={"framework": "langgraph", **self._metadata},
            )
        except Exception as e:
            logger.warning(f"[TraceIQ] LangGraph trace flush failed: {e}")
        return False  # Do not suppress exceptions


def add_tracing(graph, client, project_id: str, metadata: Optional[dict] = None):
    """
    Convenience helper: returns a wrapper object around a compiled LangGraph graph
    that automatically traces every .invoke() and .stream() call.

    Usage:
        traced = add_tracing(compiled_graph, client=bt_client, project_id="proj-123")
        result = traced.invoke(inputs)
    """
    return _TracedGraph(graph, client, project_id, metadata or {})


class _TracedGraph:
    """Thin wrapper around a compiled LangGraph graph that auto-traces calls."""

    def __init__(self, graph, client, project_id: str, metadata: dict):
        self._graph = graph
        self._client = client
        self._project_id = project_id
        self._metadata = metadata

    def invoke(self, inputs: Dict, **kwargs) -> Any:
        return trace_graph(
            self._graph, inputs, self._client, self._project_id,
            metadata=self._metadata,
        )

    def stream(self, inputs: Dict, **kwargs):
        yield from trace_graph_stream(
            self._graph, inputs, self._client, self._project_id,
            metadata=self._metadata,
        )

    def __getattr__(self, name: str):
        """Proxy any other attribute/method to the underlying graph."""
        return getattr(self._graph, name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_serialise(obj: Any, max_len: int = 4000) -> Any:
    """Convert obj to a JSON-safe dict/list/str, truncating if needed."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _safe_serialise(v) for k, v in list(obj.items())[:50]}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialise(i) for i in obj[:50]]
    s = str(obj)
    return s[:max_len] if len(s) > max_len else s
