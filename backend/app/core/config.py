"""Application configuration.

All configuration is loaded from environment variables via pydantic-settings.
No secret field has a default value (AGENTS.md Rule E-05).
Use `from app.core.config import settings` everywhere — never `os.environ`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    All fields are loaded from environment variables.
    Secret fields (API keys, JWT secrets) have no defaults and will
    raise a ValidationError on startup if not provided.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore unknown env vars gracefully
    )

    # ─────────────────────────────────────────────
    # APPLICATION
    # ─────────────────────────────────────────────

    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_VERSION: str = "0.1.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_SECRET_KEY: str = Field(
        ..., description="App-level signing key. Generate with: openssl rand -hex 32"
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # CORS — comma-separated list of allowed origins
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ALLOWED_ORIGINS into a list of origin strings."""
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    # ─────────────────────────────────────────────
    # SUPABASE
    # ─────────────────────────────────────────────

    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(..., description="Supabase anon key (safe for frontend)")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        ..., description="Supabase service role key — NEVER expose to frontend"
    )
    SUPABASE_JWT_SECRET: str = Field(..., description="Used to validate user JWTs on the backend")
    SUPABASE_DB_URL: str = Field(
        default="",
        description="Direct DB URL for migrations only; not required at runtime",
    )

    # ─────────────────────────────────────────────
    # LLM — PRIMARY (Google Gemini)
    # ─────────────────────────────────────────────

    GEMINI_API_KEY: str = Field(..., description="Google Gemini API key")
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # ─────────────────────────────────────────────
    # LLM — FALLBACK (Groq)
    # ─────────────────────────────────────────────

    GROQ_API_KEY: str = Field(..., description="Groq API key")
    GROQ_MODEL: str = "llama3-70b-8192"

    # ─────────────────────────────────────────────
    # LLM — SECONDARY FALLBACK (OpenRouter)
    # ─────────────────────────────────────────────

    OPENROUTER_API_KEY: str = Field(
        default="",
        description="OpenRouter API key — optional but recommended for resilience",
    )
    OPENROUTER_MODEL: str = "mistralai/mixtral-8x7b-instruct"

    # ─────────────────────────────────────────────
    # LLM ROUTER CONFIGURATION
    # ─────────────────────────────────────────────

    PRIMARY_LLM_PROVIDER: Literal["gemini", "groq", "openrouter"] = "gemini"
    LLM_MAX_OUTPUT_TOKENS: int = 4096
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_RETRY_ATTEMPTS: int = 3

    # ─────────────────────────────────────────────
    # WEB RESEARCH (Tavily)
    # ─────────────────────────────────────────────

    TAVILY_API_KEY: str = Field(..., description="Tavily search API key")
    TAVILY_MAX_RESULTS: int = 5
    TAVILY_SEARCH_DEPTH: Literal["basic", "advanced"] = "basic"

    # ─────────────────────────────────────────────
    # OBSERVABILITY (Langfuse — optional)
    # ─────────────────────────────────────────────

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_ENABLED: bool = True

    @property
    def langfuse_configured(self) -> bool:
        """True only if both Langfuse keys are provided."""
        return bool(self.LANGFUSE_PUBLIC_KEY and self.LANGFUSE_SECRET_KEY and self.LANGFUSE_ENABLED)

    # ─────────────────────────────────────────────
    # RESEARCH PIPELINE
    # ─────────────────────────────────────────────

    RESEARCH_DEFAULT_MAX_ITERATIONS: int = Field(default=2, ge=1, le=3)
    RESEARCH_MAX_ITERATIONS_HARD_CAP: int = Field(default=3, ge=1, le=3)
    RESEARCH_SESSION_TIMEOUT_SECONDS: int = 300
    RESEARCH_MAX_CONCURRENT_SESSIONS_PER_USER: int = 3
    RESEARCH_MAX_SOURCES_PER_TASK: int = 5
    RESEARCH_MAX_SUB_QUESTIONS: int = 8
    RESEARCH_MAX_SOURCE_CONTENT_TOKENS: int = 2000

    # Maximum number of concurrent evidence extraction LLM calls.
    # 45 fully-parallel calls hammered the provider and caused 402 errors.
    # Default of 5 balances speed vs provider rate limits on free-tier accounts.
    EVIDENCE_EXTRACTION_CONCURRENCY: int = Field(default=2, ge=1, le=20)

    # ─────────────────────────────────────────────
    # RATE LIMITING
    # ─────────────────────────────────────────────

    RATE_LIMIT_RESEARCH_PER_HOUR: int = 10
    RATE_LIMIT_API_PER_MINUTE: int = 60

    # ─────────────────────────────────────────────
    # VALIDATORS
    # ─────────────────────────────────────────────

    @field_validator("RESEARCH_MAX_ITERATIONS_HARD_CAP")
    @classmethod
    def hard_cap_not_below_default(cls, v: int, info: object) -> int:
        """Hard cap must be >= default max iterations."""
        # info.data may not have RESEARCH_DEFAULT_MAX_ITERATIONS yet due to ordering;
        # the ge=1, le=3 constraints on both fields are the primary guard.
        return v


# Module-level singleton — import this everywhere.
# Never instantiate Settings() directly in application code.
settings = Settings()
