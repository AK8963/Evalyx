"""
Tests for project endpoints.
"""
import pytest


def test_create_project(client, auth_headers):
    resp = client.post("/api/projects", json={
        "name": "my-project",
        "description": "Test"
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-project"
    assert "id" in data


def test_create_duplicate_project(client, auth_headers, test_project):
    resp = client.post("/api/projects", json={
        "name": test_project["name"],
        "description": "dup"
    }, headers=auth_headers)
    assert resp.status_code == 400


def test_list_projects(client, auth_headers, test_project):
    resp = client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(p["id"] == test_project["id"] for p in data)


def test_get_project(client, auth_headers, test_project):
    resp = client.get(f"/api/projects/{test_project['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == test_project["id"]


def test_get_project_not_found(client, auth_headers):
    resp = client.get("/api/projects/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


def test_create_project_no_auth(client):
    resp = client.post("/api/projects", json={"name": "x"})
    assert resp.status_code == 401
