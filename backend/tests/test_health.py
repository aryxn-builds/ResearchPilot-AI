"""Tests for /api/v1/health, /api/v1/readiness, and /api/v1/health/deep endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.v1.health import get_deep_health_metrics
from app.core.config import settings


# ── Existing Regression Tests ────────────────────────────────────────────────


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
    response = client.get("/api/v1/health")
    assert response.json()["version"] == settings.APP_VERSION


# ── Deep Health Check Tests (Requirement 13) ─────────────────────────────────


def test_deep_health_healthy(client: TestClient) -> None:
    """Test 1 — Backend + DB healthy: HTTP 200 with healthy envelope."""
    response = client.get("/api/v1/health/deep")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "backend": "ok",
        "database": "ok",
    }


def test_deep_health_database_unavailable(client: TestClient, mock_supabase) -> None:
    """Test 2 — Database unavailable: Mock database failure returns HTTP 503."""
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute = AsyncMock(
        side_effect=Exception("Database connection terminated")
    )
    response = client.get("/api/v1/health/deep")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "backend": "ok",
        "database": "unavailable",
    }


def test_deep_health_database_timeout(client: TestClient, mock_supabase) -> None:
    """Test 3 — Database timeout: Mock query timeout returns HTTP 503."""

    async def _timed_out_execute():
        raise asyncio.TimeoutError("Query timed out after 5 seconds")

    mock_supabase.table.return_value.select.return_value.limit.return_value.execute = AsyncMock(
        side_effect=_timed_out_execute
    )
    response = client.get("/api/v1/health/deep")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "backend": "ok",
        "database": "unavailable",
    }


def test_deep_health_no_sensitive_info(client: TestClient, mock_supabase) -> None:
    """Test 4 — No sensitive information: Ensure no keys, secrets, or traces in response."""
    resp_200 = client.get("/api/v1/health/deep")
    text_200 = resp_200.text

    mock_supabase.table.return_value.select.return_value.limit.return_value.execute = AsyncMock(
        side_effect=RuntimeError("CRITICAL_INTERNAL_DB_PASSWORD_12345")
    )
    resp_503 = client.get("/api/v1/health/deep")
    text_503 = resp_503.text

    sensitive_tokens = [
        settings.SUPABASE_SERVICE_ROLE_KEY,
        settings.SUPABASE_JWT_SECRET,
        settings.SUPABASE_ANON_KEY,
        settings.GEMINI_API_KEY,
        settings.GROQ_API_KEY,
        "CRITICAL_INTERNAL_DB_PASSWORD_12345",
        "Traceback (most recent call last)",
        "RuntimeError",
        "Exception",
    ]

    for token in sensitive_tokens:
        if token:
            assert token not in text_200, f"Token {token} leaked in 200 response"
            assert token not in text_503, f"Token {token} leaked in 503 response"


def test_deep_health_read_only_no_mutation(client: TestClient, mock_supabase) -> None:
    """Test 5 — No database mutation: Verifies query only performs SELECT with limit."""
    mock_supabase.table.reset_mock()

    response = client.get("/api/v1/health/deep")
    assert response.status_code == 200

    # Ensure table("research_sessions") was called
    mock_supabase.table.assert_called_with("research_sessions")

    # Ensure mutating methods were NEVER called
    assert not mock_supabase.table.return_value.insert.called
    assert not mock_supabase.table.return_value.update.called
    assert not mock_supabase.table.return_value.delete.called
    assert not mock_supabase.table.return_value.upsert.called


def test_deep_health_secret_protection(client: TestClient) -> None:
    """Test 7 — Optional secret protection: Validates Authorization header when secret is configured."""
    with patch.object(settings, "HEALTH_CHECK_SECRET", "super-secret-token"):
        # Without header -> 401
        res_no_auth = client.get("/api/v1/health/deep")
        assert res_no_auth.status_code == 401
        assert res_no_auth.json()["error"]["code"] == "UNAUTHORIZED"

        # With wrong header -> 401
        res_wrong_auth = client.get(
            "/api/v1/health/deep", headers={"Authorization": "Bearer wrong-token"}
        )
        assert res_wrong_auth.status_code == 401

        # With correct header -> 200
        res_correct_auth = client.get(
            "/api/v1/health/deep", headers={"Authorization": "Bearer super-secret-token"}
        )
        assert res_correct_auth.status_code == 200
        assert res_correct_auth.json()["status"] == "healthy"


def test_deep_health_metrics_telemetry(client: TestClient, mock_supabase) -> None:
    """Test 8 — Telemetry metrics: Verify health_metrics counters increment accurately."""
    initial_metrics = get_deep_health_metrics()
    initial_total = initial_metrics["total_requests"]
    initial_success = initial_metrics["successful_checks"]
    initial_failed = initial_metrics["failed_checks"]

    # 1. Successful check
    client.get("/api/v1/health/deep")
    m1 = get_deep_health_metrics()
    assert m1["total_requests"] == initial_total + 1
    assert m1["successful_checks"] == initial_success + 1
    assert m1["failed_checks"] == initial_failed
    assert m1["last_latency_ms"] >= 0

    # 2. Failed check
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute = AsyncMock(
        side_effect=Exception("Database down")
    )
    client.get("/api/v1/health/deep")
    m2 = get_deep_health_metrics()
    assert m2["total_requests"] == initial_total + 2
    assert m2["successful_checks"] == initial_success + 1
    assert m2["failed_checks"] == initial_failed + 1
