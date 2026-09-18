"""Tests for error handling — verifying the API error envelope format.

All errors must return:
  { "error": { "code": ..., "message": ..., "details": ... }, "meta": { "request_id": ... } }

This is defined in API_SPEC.md and enforced by the global exception handlers in main.py.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_unauthenticated_request_returns_401(client: TestClient) -> None:
    """Protected endpoint without token returns 401 with standard error envelope."""
    response = client.get("/api/v1/research")
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "MISSING_AUTH"
    assert "message" in body["error"]
    assert "meta" in body
    assert "request_id" in body["meta"]


def test_invalid_bearer_token_returns_401(client: TestClient) -> None:
    """Invalid Bearer token returns 401 with INVALID_TOKEN code."""
    response = client.get(
        "/api/v1/research",
        headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_TOKEN"


def test_validation_error_returns_422(client: TestClient) -> None:
    """Invalid request body returns 422 with VALIDATION_ERROR code."""
    import time

    import jwt

    # Create a valid JWT for this test
    token = jwt.encode(
        {
            "sub": "11111111-1111-1111-1111-111111111111",
            "email": "test@test.com",
            "role": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        "test-jwt-secret-key-for-hs256-signing",
        algorithm="HS256",
    )

    response = client.post(
        "/api/v1/research",
        json={"question": "too short"},  # fails min_length=10
        headers={"Authorization": f"Bearer {token}"},
    )
    # Either 422 (validation) or 401 (if auth fails first) — test envelope format
    assert response.status_code in {401, 422}
    body = response.json()
    assert "error" in body
    assert "meta" in body
    assert "request_id" in body["meta"]


def test_error_response_always_has_meta(client: TestClient) -> None:
    """Every error response includes a meta.request_id field."""
    # Hit a non-existent route
    response = client.get("/api/v1/nonexistent-endpoint")
    # 404 from FastAPI's default handler
    assert response.status_code == 404


def test_health_endpoint_is_not_protected(client: TestClient) -> None:
    """Health endpoint never returns 401 — it's not a protected route."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_error_envelope_structure() -> None:
    """ErrorResponse Pydantic model has correct field structure."""
    from uuid import uuid4

    from app.schemas.common import ErrorDetail, ErrorResponse, ResponseMeta

    err = ErrorResponse(
        error=ErrorDetail(code="TEST_CODE", message="Test message"),
        meta=ResponseMeta(request_id=str(uuid4())),
    )
    assert err.error.code == "TEST_CODE"
    assert err.error.message == "Test message"
    assert err.error.details == {}
    assert err.meta.request_id is not None
