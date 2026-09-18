"""Unit and integration tests for production CORS preflight handling."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def cors_app_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a TestClient with production-like Vercel CORS origins configured."""
    from app.core import config

    monkeypatch.setattr(
        config.settings,
        "CORS_ALLOWED_ORIGINS",
        "https://researchpilot-ai.vercel.app,https://custom-domain.com/",
    )
    monkeypatch.setattr(
        config.settings,
        "CORS_ORIGIN_REGEX",
        r"^https://researchpilot-.*\.vercel\.app$",
    )
    app = create_app()
    return TestClient(app)


def test_cors_preflight_allowed_origin_success(cors_app_client: TestClient) -> None:
    """OPTIONS request from an allowed production Vercel origin must return 200 with CORS headers."""
    response = cors_app_client.options(
        "/api/v1/research",
        headers={
            "Origin": "https://researchpilot-ai.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type, idempotency-key",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://researchpilot-ai.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_trailing_slash_normalized(cors_app_client: TestClient) -> None:
    """Origin configured with trailing slash must match browser origin without trailing slash."""
    response = cors_app_client.options(
        "/api/v1/research",
        headers={
            "Origin": "https://custom-domain.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://custom-domain.com"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_arbitrary_client_headers_allowed(cors_app_client: TestClient) -> None:
    """Browser/client telemetry headers (e.g., sentry-trace, baggage, x-client-info) must not trigger 400."""
    response = cors_app_client.options(
        "/api/v1/research",
        headers={
            "Origin": "https://researchpilot-ai.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type, x-client-info, sentry-trace, baggage",
        },
    )
    assert response.status_code == 200
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "x-client-info" in allow_headers


def test_cors_preflight_disallowed_origin_rejected(cors_app_client: TestClient) -> None:
    """OPTIONS request from an unauthorized origin must be rejected (status 400 or no allow-origin)."""
    response = cors_app_client.options(
        "/api/v1/research",
        headers={
            "Origin": "https://unauthorized-evil-site.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    # Starlette CORSMiddleware returns 400 for disallowed CORS origins
    assert response.status_code == 400 or "access-control-allow-origin" not in response.headers


def test_cors_preflight_origin_regex_preview_branch(cors_app_client: TestClient) -> None:
    """Dynamic preview deployment origins matching CORS_ORIGIN_REGEX must succeed."""
    response = cors_app_client.options(
        "/api/v1/research",
        headers={
            "Origin": "https://researchpilot-git-feature-preview.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://researchpilot-git-feature-preview.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_origins_list_json_and_alias_support() -> None:
    """Settings must parse JSON array format and CORS_ORIGINS alias cleanly."""
    settings_json = Settings(
        APP_SECRET_KEY="test-key-32-chars-minimum-value!",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY="service",
        SUPABASE_JWT_SECRET="secret",
        GEMINI_API_KEY="gem",
        GROQ_API_KEY="groq",
        TAVILY_API_KEY="tav",
        CORS_ORIGINS='["https://preview-1.vercel.app/", "https://preview-2.vercel.app"]',
    )
    origins = settings_json.cors_origins_list
    assert "https://preview-1.vercel.app" in origins  # trailing slash stripped
    assert "https://preview-2.vercel.app" in origins
    assert len(origins) == 2
