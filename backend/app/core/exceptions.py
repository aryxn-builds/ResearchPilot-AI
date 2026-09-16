"""Custom exception hierarchy for ResearchPilot AI.

All application errors inherit from AppError.
FastAPI exception handlers convert these to the standard API error format
defined in API_SPEC.md:

  { "error": { "code": ..., "message": ..., "details": ... }, "meta": { ... } }

Never use bare `except Exception` — always catch specific AppError subclasses.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all application-level errors.

    Args:
        message: Human-readable error description.
        code: Machine-readable error code (see API_SPEC.md Standard Error Codes).
        status_code: HTTP status code to return.
        details: Optional extra context (never include secrets or stack traces).
    """

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


# ─────────────────────────────────────────────
# 400 — Bad Request
# ─────────────────────────────────────────────


class ValidationError(AppError):
    """Request body or query param failed validation."""

    def __init__(
        self, message: str = "Request validation failed.", details: dict | None = None
    ) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=400, details=details)


class InvalidQuestionError(AppError):
    """Research question is empty or exceeds character limit."""

    def __init__(self, message: str = "Research question is invalid.") -> None:
        super().__init__(message=message, code="INVALID_QUESTION", status_code=400)


# ─────────────────────────────────────────────
# 401 — Unauthorized
# ─────────────────────────────────────────────


class MissingAuthError(AppError):
    """No Authorization header provided."""

    def __init__(self, message: str = "Authorization header is required.") -> None:
        super().__init__(message=message, code="MISSING_AUTH", status_code=401)


class InvalidTokenError(AppError):
    """JWT is invalid, expired, or malformed."""

    def __init__(self, message: str = "The provided token is invalid or has expired.") -> None:
        super().__init__(message=message, code="INVALID_TOKEN", status_code=401)


# ─────────────────────────────────────────────
# 403 — Forbidden
# ─────────────────────────────────────────────


class ForbiddenError(AppError):
    """Authenticated but not authorized for this resource."""

    def __init__(
        self, message: str = "You do not have permission to access this resource."
    ) -> None:
        super().__init__(message=message, code="FORBIDDEN", status_code=403)


# ─────────────────────────────────────────────
# 404 — Not Found
# ─────────────────────────────────────────────


class NotFoundError(AppError):
    """Generic resource not found."""

    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404)


class ResearchNotFoundError(AppError):
    """Research session ID not found or belongs to another user."""

    def __init__(self, research_id: str | None = None) -> None:
        message = (
            f"Research session '{research_id}' was not found."
            if research_id
            else "Research session was not found."
        )
        super().__init__(message=message, code="RESEARCH_NOT_FOUND", status_code=404)


class ReportNotFoundError(AppError):
    """Session exists but report has not been generated yet."""

    def __init__(self, research_id: str | None = None) -> None:
        message = (
            f"Report for research session '{research_id}' has not been generated yet."
            if research_id
            else "Report has not been generated yet."
        )
        super().__init__(message=message, code="REPORT_NOT_FOUND", status_code=404)


# ─────────────────────────────────────────────
# 409 — Conflict
# ─────────────────────────────────────────────


class SessionAlreadyExistsError(AppError):
    """Idempotency key collision."""

    def __init__(
        self, message: str = "A research session with this idempotency key already exists."
    ) -> None:
        super().__init__(message=message, code="SESSION_ALREADY_EXISTS", status_code=409)


class MaxSessionsReachedError(AppError):
    """User has reached the concurrent session limit."""

    def __init__(self, limit: int = 3) -> None:
        super().__init__(
            message=f"You have reached the maximum of {limit} concurrent research sessions.",
            code="MAX_SESSIONS_REACHED",
            status_code=409,
        )


# ─────────────────────────────────────────────
# 422 — Unprocessable Entity
# ─────────────────────────────────────────────


class UnprocessableError(AppError):
    """Request is valid JSON but semantically invalid."""

    def __init__(
        self, message: str = "The request could not be processed.", details: dict | None = None
    ) -> None:
        super().__init__(message=message, code="UNPROCESSABLE", status_code=422, details=details)


# ─────────────────────────────────────────────
# 429 — Rate Limited
# ─────────────────────────────────────────────


class RateLimitError(AppError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded. Please try again later.") -> None:
        super().__init__(message=message, code="RATE_LIMITED", status_code=429)


# ─────────────────────────────────────────────
# 500 — Internal Server Error
# ─────────────────────────────────────────────


class InternalError(AppError):
    """Unhandled server error. Details are never sent to the client."""

    def __init__(self, message: str = "An internal server error occurred.") -> None:
        super().__init__(message=message, code="INTERNAL_ERROR", status_code=500)


# ─────────────────────────────────────────────
# 503 — Service Unavailable
# ─────────────────────────────────────────────


class ResearchUnavailableError(AppError):
    """All LLM providers are currently unavailable."""

    def __init__(
        self,
        message: str = "The research service is temporarily unavailable. Please try again shortly.",
    ) -> None:
        super().__init__(message=message, code="RESEARCH_UNAVAILABLE", status_code=503)


# Alias used in AGENTS.md and ARCHITECTURE.md
ProviderExhaustedError = ResearchUnavailableError
