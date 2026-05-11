"""
Tests for evaluation endpoints.
"""
import pytest


def test_create_eval(client, auth_headers, test_project):
    resp = client.post("/api/evals", json={
        "project_id": test_project["id"],
        "name": "eval-v1",
        "description": "First eval run",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "eval-v1"
    assert data["status"] in ("pending", "running")


def test_list_evals(client, auth_headers, test_project):
    client.post("/api/evals", json={
        "project_id": test_project["id"],
        "name": "eval-list-test",
    }, headers=auth_headers)
    resp = client.get(f"/api/evals?project_id={test_project['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_eval(client, auth_headers, test_project):
    create = client.post("/api/evals", json={
        "project_id": test_project["id"],
        "name": "eval-get-test",
    }, headers=auth_headers)
    eval_id = create.json()["id"]

    resp = client.get(f"/api/evals/{eval_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == eval_id


def test_eval_no_auth(client, test_project):
    resp = client.get(f"/api/evals?project_id={test_project['id']}")
    assert resp.status_code == 401
