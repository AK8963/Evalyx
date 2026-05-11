"""
Tests for trace ingestion and retrieval.
"""
import pytest


def _make_trace(project_id, model="gpt-4", status="success"):
    return {
        "project_id": project_id,
        "input_data": {"messages": [{"role": "user", "content": "Hello"}]},
        "output_data": {"content": "Hi there!"},
        "model": model,
        "latency_ms": 250.5,
        "total_tokens": 42,
        "status": status,
    }


def test_create_trace(client, auth_headers, test_project):
    resp = client.post("/api/traces", json=_make_trace(test_project["id"]),
                       headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == test_project["id"]
    assert data["model"] == "gpt-4"
    assert "id" in data


def test_list_traces(client, auth_headers, test_project):
    # Create two traces
    client.post("/api/traces", json=_make_trace(test_project["id"]), headers=auth_headers)
    client.post("/api/traces", json=_make_trace(test_project["id"], model="claude-3"), headers=auth_headers)

    resp = client.get(f"/api/traces?project_id={test_project['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_list_traces_model_filter(client, auth_headers, test_project):
    client.post("/api/traces", json=_make_trace(test_project["id"], model="gpt-filter-test"), headers=auth_headers)
    resp = client.get(
        f"/api/traces?project_id={test_project['id']}&model=gpt-filter-test",
        headers=auth_headers
    )
    assert resp.status_code == 200
    for t in resp.json():
        assert t["model"] == "gpt-filter-test"


def test_get_trace(client, auth_headers, test_project):
    create_resp = client.post("/api/traces", json=_make_trace(test_project["id"]),
                              headers=auth_headers)
    trace_id = create_resp.json()["id"]

    resp = client.get(f"/api/traces/{trace_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == trace_id


def test_batch_ingest(client, auth_headers, test_project):
    traces = [_make_trace(test_project["id"]) for _ in range(5)]
    resp = client.post("/api/traces/batch", json=traces, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["count"] == 5
    assert len(data["trace_ids"]) == 5


def test_delete_trace(client, auth_headers, test_project):
    create_resp = client.post("/api/traces", json=_make_trace(test_project["id"]),
                              headers=auth_headers)
    trace_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/traces/{trace_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/traces/{trace_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_trace_access_denied(client, auth_headers, test_project):
    """Another user's project should be inaccessible."""
    # Register second user
    resp = client.post("/api/auth/register", json={"email": "user2@example.com", "name": "U2"})
    token2 = resp.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Try to list traces from first user's project
    resp = client.get(f"/api/traces?project_id={test_project['id']}", headers=headers2)
    assert resp.status_code == 403
