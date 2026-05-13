"""
TrustBrain Python SDK
Trace ingestion and evaluation for LLM applications.
"""

from .client import TrustBrainClient, Trace, Span
from .decorators import traciq_trace, TraceContext

# Convenience aliases
trace = traciq_trace
TrustBrain = TrustBrainClient  # canonical import alias


def score(name: str):
    """Decorator to mark a function as a scoring function.

    Usage::

        @score(name="accuracy")
        def accuracy(output, expected):
            return 1.0 if output == expected else 0.0
    """
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        wrapper._score_name = name
        return wrapper

    return decorator


def init(api_key: str, base_url: str = "http://localhost:8000") -> TrustBrainClient:
    """Create and return a configured TrustBrainClient.

    Usage::

        import trustbrain
        client = trustbrain.init(api_key="tb_...", base_url="http://localhost:8000")
        client.trace(project_name="my_project", model="gpt-4o", input_data=..., output_data=...)
        client.flush()
    """
    return TrustBrainClient(api_key=api_key, base_url=base_url)


# Integrations (optional — only available if dependencies are installed)
try:
    from .integrations.openai import patch_openai
    from .integrations.anthropic import patch_anthropic
    from .integrations.langchain import TraceIQCallbackHandler
    _integrations_available = True
except ImportError:
    _integrations_available = False

__version__ = "0.1.0"

__all__ = [
    # Core
    "TrustBrainClient",
    "TrustBrain",
    "Trace",
    "Span",
    "init",
    "trace",
    "score",
    "traciq_trace",
    "TraceContext",
    # Integrations (if available)
    "patch_openai",
    "patch_anthropic",
    "TraceIQCallbackHandler",
]
