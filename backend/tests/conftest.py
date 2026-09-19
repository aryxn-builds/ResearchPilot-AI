"""Shared test fixtures and configuration.

Provides:
  - test_settings: Overridden settings with fake values (no real API keys needed)
  - app: FastAPI test application with mocked dependencies
  - client: httpx AsyncClient for making test requests
  - mock_supabase: Pre-patched Supabase client

AGENTS.md Rule AI-13: Never fabricate test results. Run tests to verify.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# ── Set up test environment BEFORE importing any app modules ─────────────────
# This prevents pydantic-settings from failing due to missing env vars.

_TEST_ENV = {
    "APP_ENV": "development",
    "APP_SECRET_KEY": "test-secret-key-32-chars-minimum!",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "SUPABASE_JWT_SECRET": "test-jwt-secret-key-for-hs256-signing",
    "GEMINI_API_KEY": "test-gemini-key",
    "GROQ_API_KEY": "test-groq-key",
    "TAVILY_API_KEY": "test-tavily-key",
    "LANGFUSE_ENABLED": "false",
    "LLM_RETRY_BASE_DELAY": "0.001",
}

for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)

# ── Now import app modules (after env is set) ────────────────────────────────

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return Settings loaded from the test environment (no .env file)."""
    return Settings(**dict(_TEST_ENV))


@pytest.fixture
def mock_supabase():
    """Return a mock Supabase service client that returns empty results."""
    mock = MagicMock()
    # Default: empty result with no count
    mock_result = MagicMock()
    mock_result.data = []
    mock_result.count = 0

    # Chain table().select()...execute() → mock_result
    mock.table.return_value.select.return_value.eq.return_value.is_.return_value.in_.return_value.execute = AsyncMock(
        return_value=mock_result
    )
    mock.table.return_value.select.return_value.limit.return_value.execute = AsyncMock(
        return_value=mock_result
    )
    return mock


@pytest.fixture
def app_with_mocked_db(mock_supabase):
    """FastAPI app with Supabase clients mocked out."""
    with (
        patch("app.core.database.init_supabase_clients", new=AsyncMock()),
        patch("app.core.database.close_supabase_clients", new=AsyncMock()),
        patch("app.core.database.get_service_client", return_value=mock_supabase),
        patch("app.core.database.get_anon_client", return_value=mock_supabase),
    ):
        application = create_app()
        yield application


@pytest.fixture
def client(app_with_mocked_db) -> TestClient:
    """Synchronous test client (no lifespan triggered)."""
    return TestClient(app_with_mocked_db, raise_server_exceptions=False)


@pytest.fixture
async def async_client(app_with_mocked_db) -> AsyncClient:
    """Async test client for endpoints requiring async patterns."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_mocked_db), base_url="http://test"
    ) as ac:
        yield ac
