"""Request logging middleware.

Attaches a unique X-Request-ID to every request and logs:
  - method, path, status_code, duration_ms
  - Never logs Authorization headers, query params containing tokens,
    or request/response bodies (they may contain sensitive data).

Compliant with AGENTS.md logging rules.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with a unique request_id, latency, and status code.

    The request_id is added to structlog context so all logs emitted during
    request processing are correlated.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request: attach ID, log start, call handler, log completion."""
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        # Bind request_id into structlog context for this request's lifetime
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Attach to request state so route handlers can access it
        request.state.request_id = request_id

        response: Response
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                "request_error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Skip logging for health checks to reduce noise
        if request.url.path not in {"/api/v1/health", "/health"}:
            logger.info(
                "request_complete",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        # Attach request ID to response headers for client-side correlation
        response.headers["X-Request-ID"] = request_id

        return response
