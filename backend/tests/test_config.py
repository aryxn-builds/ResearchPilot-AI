"""Tests for application settings and configuration validation."""

from __future__ import annotations


def test_settings_load_from_env() -> None:
    """Settings must load all required fields from environment variables."""
    from app.core.config import settings

    # These fields are required (no defaults)
    assert settings.SUPABASE_URL
    assert settings.SUPABASE_ANON_KEY
    assert settings.SUPABASE_SERVICE_ROLE_KEY
    assert settings.SUPABASE_JWT_SECRET
    assert settings.GEMINI_API_KEY
    assert settings.GROQ_API_KEY
    assert settings.TAVILY_API_KEY


def test_cors_origins_list_parses_correctly() -> None:
    """cors_origins_list must split CORS_ALLOWED_ORIGINS on commas."""
    from app.core.config import Settings

    s = Settings(
        **{
            "APP_SECRET_KEY": "test-key-32-chars-minimum-value!",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_ANON_KEY": "anon",
            "SUPABASE_SERVICE_ROLE_KEY": "service",
            "SUPABASE_JWT_SECRET": "secret",
            "GEMINI_API_KEY": "gem",
            "GROQ_API_KEY": "groq",
            "TAVILY_API_KEY": "tav",
            "CORS_ALLOWED_ORIGINS": "http://localhost:3000,http://localhost:3001",
        }
    )
    origins = s.cors_origins_list
    assert "http://localhost:3000" in origins
    assert "http://localhost:3001" in origins
    assert len(origins) == 2


def test_langfuse_configured_false_when_keys_missing() -> None:
    """langfuse_configured must be False when Langfuse keys are not set."""
    from app.core.config import Settings

    s = Settings(
        **{
            "APP_SECRET_KEY": "test-key-32-chars-minimum-value!",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_ANON_KEY": "anon",
            "SUPABASE_SERVICE_ROLE_KEY": "service",
            "SUPABASE_JWT_SECRET": "secret",
            "GEMINI_API_KEY": "gem",
            "GROQ_API_KEY": "groq",
            "TAVILY_API_KEY": "tav",
            # Langfuse keys absent — defaults to ""
        }
    )
    assert s.langfuse_configured is False


def test_research_iteration_hard_cap_constraints() -> None:
    """RESEARCH_MAX_ITERATIONS_HARD_CAP must be between 1 and 3."""
    from app.core.config import settings

    assert 1 <= settings.RESEARCH_MAX_ITERATIONS_HARD_CAP <= 3
    assert 1 <= settings.RESEARCH_DEFAULT_MAX_ITERATIONS <= 3
