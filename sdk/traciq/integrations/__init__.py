"""
Auto-instrumentation integrations for the TraceIQ SDK.
"""
from sdk.traciq.integrations.openai import patch_openai
from sdk.traciq.integrations.anthropic import patch_anthropic

# Phase 2: agent framework integrations (imported lazily to avoid hard deps)
try:
    from sdk.traciq.integrations.crewai import trace_crew, TraceIQCrewCallback
    from sdk.traciq.integrations.langgraph import trace_graph, trace_graph_stream, TraceIQLangGraphTracer, add_tracing
    __all__ = [
        "patch_openai", "patch_anthropic",
        "trace_crew", "TraceIQCrewCallback",
        "trace_graph", "trace_graph_stream", "TraceIQLangGraphTracer", "add_tracing",
    ]
except ImportError:
    __all__ = ["patch_openai", "patch_anthropic"]
