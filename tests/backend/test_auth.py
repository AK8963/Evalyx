"""
Tests for authentication endpoints.
"""
import pytest


def test_register_user(client):
    resp = client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "name": "New User"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email(client, auth_headers):
    resp = client.post("/api/auth/register", json={
        "email": "testuser@example.com",
        "name": "Dup"
    })
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


def test_login_success(client, auth_headers):
    resp = client.post("/api/auth/login", json={"email": "testuser@example.com"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_unknown_user(client):
    resp = client.post("/api/auth/login", json={"email": "nobody@example.com"})
    assert resp.status_code == 401


def test_get_me(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "testuser@example.com"
    assert "id" in data


def test_get_me_no_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_get_me_bad_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
