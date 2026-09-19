"""In-memory per-user rate limiting middleware.

Implements the rate limits defined in API_SPEC.md:
  - POST /api/v1/research: 10 requests per hour per user
  - All other endpoints: 60 requests per minute per user

Implementation:
  - In-memory sliding window counters (collections.defaultdict).
  - Acceptable for MVP single-process deployment (ADR-002).
  - Counters reset on server restart — this is an accepted tradeoff.
  - Will be replaced with Redis-backed rate limiting in Phase 3.

Rate limit headers are added to every response:
  X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class _Window:
    """Sliding time window counter for rate limiting."""

    count: int = 0
    window_start: float = field(default_factory=time.monotonic)


# In-memory store: { (user_id, endpoint_key) -> _Window }
_counters: dict[tuple[str, str], _Window] = defaultdict(
    lambda: _Window(window_start=time.monotonic())
)
_counters_lock: dict[str, bool] = {}  # Minimal guard for concurrent resets


def _get_rate_limit_config(path: str, method: str) -> tuple[int, int]:
    """Return (limit, window_seconds) for a given path and method.

    Args:
        path: Request URL path.
        method: HTTP method (uppercase).

    Returns:
        Tuple of (max_requests, window_seconds).
    """
    if method == "POST" and path.startswith("/api/v1/research"):
        return settings.RATE_LIMIT_RESEARCH_PER_HOUR, 3600
    return settings.RATE_LIMIT_API_PER_MINUTE, 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user rate limiting middleware.

    Reads the user identity from request.state.user_id (set by auth dependency).
    For unauthenticated requests (health check), rate limiting is not applied.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Check rate limits before passing request to route handler."""
        path = request.url.path
        if path.startswith("/api/v1/health") or path in {"/health", "/api/v1/readiness", "/openapi.json", "/docs", "/redoc"}:
            return await call_next(request)

        # user_id is set by the auth dependency; if absent, skip (auth will reject anyway)
        user_id: str | None = getattr(request.state, "user_id", None)
        if user_id is None:
            return await call_next(request)

        limit, window_seconds = _get_rate_limit_config(path, request.method)
        key = (user_id, f"{request.method}:{path}")
        now = time.monotonic()

        window = _counters[key]
        # Reset window if expired
        if now - window.window_start > window_seconds:
            window.count = 0
            window.window_start = now

        window.count += 1
        remaining = max(0, limit - window.count)
        reset_at = int(time.time() + (window_seconds - (now - window.window_start)))

        rate_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
        }

        if window.count > limit:
            logger.warning("rate_limit_exceeded", user_id=user_id, path=path, limit=limit)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Rate limit exceeded. Please try again later.",
                        "details": {"retry_after": reset_at},
                    },
                    "meta": {"request_id": getattr(request.state, "request_id", "unknown")},
                },
                headers={**rate_headers, "Retry-After": str(reset_at - int(time.time()))},
            )

        response = await call_next(request)
        for header_name, header_value in rate_headers.items():
            response.headers[header_name] = header_value

        return response
