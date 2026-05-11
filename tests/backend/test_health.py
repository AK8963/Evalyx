"""
Tests for the health and metrics endpoints.
"""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_metrics_endpoint(client):
    """Metrics endpoint should return 200 or 501 depending on whether
    prometheus_client is installed."""
    resp = client.get("/metrics")
    assert resp.status_code in (200, 501)
    if resp.status_code == 200:
        # prometheus text format
        assert "http_requests_total" in resp.text or "#" in resp.text
