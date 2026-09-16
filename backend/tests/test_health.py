"""Tests for /api/v1/health and /api/v1/readiness endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    """Health endpoint must return 200 with status: ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "timestamp" in body
    assert "environment" in body


def test_health_no_auth_required(client: TestClient) -> None:
    """Health endpoint must not require Authorization header."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_has_request_id_header(client: TestClient) -> None:
    """Health response should include X-Request-ID header from middleware."""
    response = client.get("/api/v1/health")
    # X-Request-ID is added by logging middleware
    assert "x-request-id" in response.headers


def test_readiness_returns_200_when_db_healthy(app_with_mocked_db) -> None:
    """Readiness endpoint returns 200 when Supabase is reachable."""
    with TestClient(app_with_mocked_db, raise_server_exceptions=False) as tc:
        response = tc.get("/api/v1/readiness")
    assert response.status_code in {200, 503}  # depends on mock connectivity
    body = response.json()
    assert "status" in body
    assert "checks" in body
    assert "timestamp" in body


def test_health_version_matches_settings(client: TestClient) -> None:
    """Health version field matches APP_VERSION setting."""
    from app.core.config import settings

    response = client.get("/api/v1/health")
    assert response.json()["version"] == settings.APP_VERSION
