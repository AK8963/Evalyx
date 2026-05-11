"""
Tests for the TraceIQ Python SDK client.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock
import httpx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(project_id=None, api_key="test-key", base_url="http://localhost:8000"):
    from sdk.traciq.client import TraceIQClient
    pid = project_id or str(uuid.uuid4())
    return TraceIQClient(project_id=pid, api_key=api_key, base_url=base_url), pid


# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------

def test_client_init():
    client, pid = _make_client()
    assert client.project_id == pid
    assert client.api_key == "test-key"


def test_client_missing_project_id():
    from sdk.traciq.client import TraceIQClient
    with pytest.raises((TypeError, ValueError)):
        TraceIQClient(api_key="k")  # project_id required


# ---------------------------------------------------------------------------
# Trace construction
# ---------------------------------------------------------------------------

def test_trace_has_id():
    from sdk.traciq.client import Trace
    t = Trace(project_id="proj-1", model="gpt-4")
    assert t.id is not None
    assert len(t.id) == 36  # UUID


def test_trace_to_dict():
    from sdk.traciq.client import Trace
    t = Trace(project_id="proj-1", model="gpt-4", status="success")
    d = t.to_dict()
    assert d["project_id"] == "proj-1"
    assert d["model"] == "gpt-4"


# ---------------------------------------------------------------------------
# log() – success path (mocked HTTP)
# ---------------------------------------------------------------------------

def test_log_success(respx_mock):
    """SDK.log() should POST to /api/traces and return the trace ID."""
    pytest.importorskip("respx")
    from sdk.traciq.client import TraceIQClient
    pid = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    respx_mock.post("http://localhost:8000/api/traces").mock(
        return_value=httpx.Response(201, json={"id": trace_id, "project_id": pid})
    )

    client = TraceIQClient(project_id=pid, api_key="key", base_url="http://localhost:8000")
    result = client.log(input_data={"q": "hi"}, output_data={"a": "hello"}, model="gpt-4")
    assert result == trace_id


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def test_trace_decorator_runs_function():
    from sdk.traciq.decorators import trace

    @trace(project_id="proj-x")
    def add(a, b):
        return a + b

    with patch("sdk.traciq.decorators.TraceIQClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        result = add(1, 2)

    assert result == 3


def test_score_decorator():
    from sdk.traciq.decorators import score

    @score(name="accuracy")
    def accuracy_fn(output, expected):
        return 1.0 if output == expected else 0.0

    result = accuracy_fn("hello", "hello")
    assert result == 1.0
