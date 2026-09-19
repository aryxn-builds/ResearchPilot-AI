"""Health check endpoints.

GET /api/v1/health       — Liveness probe (always returns 200 if server is up)
GET /api/v1/readiness    — Readiness probe (checks Supabase connectivity)
GET /api/v1/health/deep  — Deep health probe (verifies backend + Supabase for uptime monitors)

These endpoints are excluded from rate limiting and user auth requirements.
They are excluded from access logs to reduce noise (see middleware/logging.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import check_database_connectivity
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 OK if the server process is running. No auth required.",
    response_description="Service is live",
    status_code=200,
)
async def health_check() -> JSONResponse:
    """Liveness probe — used by load balancers and container orchestrators.

    Returns HTTP 200 with a minimal JSON body as long as the process is alive.
    """
    return JSONResponse(
        content={
            "status": "ok",
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
    )


@router.get(
    "/readiness",
    summary="Readiness probe",
    description="Returns 200 if all critical dependencies are reachable. No auth required.",
    status_code=200,
)
async def readiness_check() -> JSONResponse:
    """Readiness probe — checks that Supabase is reachable.

    Used by container orchestrators to determine if the instance is ready
    to receive traffic. Fails fast if dependencies are unavailable.
    """
    from app.core.database import get_service_client

    checks: dict[str, str] = {}
    overall_ok = True

    # Check Supabase connectivity
    try:
        client = get_service_client()
        # Lightweight query — only retrieves zero rows
        await client.table("research_sessions").select("id").limit(0).execute()
        checks["supabase"] = "ok"
    except RuntimeError:
        # Client not initialized yet (startup edge case)
        checks["supabase"] = "initializing"
        overall_ok = False
    except Exception as exc:
        checks["supabase"] = f"error: {type(exc).__name__}"
        overall_ok = False
        logger.warning("readiness_supabase_failure", error=str(exc))

    status_code = 200 if overall_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if overall_ok else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        },
    )


# ─────────────────────────────────────────────
# Deep Health Check — Uptime Monitor & Supabase Keep-Alive
# ─────────────────────────────────────────────


class DeepHealthResponse(BaseModel):
    """Response envelope for GET /api/v1/health/deep."""

    status: str = Field(..., description="'healthy' or 'unhealthy'")
    backend: str = Field(..., description="'ok'")
    database: str = Field(..., description="'ok' or 'unavailable'")


@dataclass
class DeepHealthMetrics:
    """In-memory telemetry counters for deep health check monitoring."""

    total_requests: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    last_latency_ms: float = 0.0


health_metrics = DeepHealthMetrics()


def get_deep_health_metrics() -> dict[str, float | int]:
    """Retrieve current deep health check metrics."""
    return {
        "total_requests": health_metrics.total_requests,
        "successful_checks": health_metrics.successful_checks,
        "failed_checks": health_metrics.failed_checks,
        "last_latency_ms": health_metrics.last_latency_ms,
    }


@router.get(
    "/health/deep",
    summary="Deep health check & Supabase connectivity verification",
    description=(
        "Verifies backend process liveliness and real read-only connectivity to Supabase. "
        "Performs a minimal SELECT id FROM research_sessions LIMIT 1. "
        "Does NOT execute any research workflows, LLMs, or web searches. "
        "Returns HTTP 200 if healthy, or HTTP 503 if Supabase is unreachable/timed out."
    ),
    response_model=DeepHealthResponse,
    responses={
        200: {
            "description": "Backend and database are healthy",
            "content": {
                "application/json": {
                    "example": {"status": "healthy", "backend": "ok", "database": "ok"}
                }
            },
        },
        503: {
            "description": "Backend is alive but database connectivity failed",
            "content": {
                "application/json": {
                    "example": {"status": "unhealthy", "backend": "ok", "database": "unavailable"}
                }
            },
        },
    },
)
async def deep_health_check(request: Request) -> JSONResponse:
    """Deep infrastructure availability probe for external schedulers and uptime monitors.

    Checks:
      1. Backend process is running.
      2. Supabase configuration exists and client is initialized.
      3. Bounded read-only query executes successfully against Supabase.
    """
    # Optional secret validation if HEALTH_CHECK_SECRET is configured
    expected_secret = getattr(settings, "HEALTH_CHECK_SECRET", "").strip()
    if expected_secret:
        auth_header = request.headers.get("authorization", "")
        if auth_header != f"Bearer {expected_secret}":
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid health check secret.",
                    }
                },
            )

    t0 = time.perf_counter()
    timeout = getattr(settings, "DATABASE_HEALTH_CHECK_TIMEOUT_SECONDS", 5.0)

    try:
        db_ok = await check_database_connectivity(timeout=timeout)
    except Exception as exc:
        logger.exception("deep_health_check_unexpected_failure", error=str(exc))
        db_ok = False

    duration_ms = (time.perf_counter() - t0) * 1000

    # Update in-memory telemetry
    health_metrics.total_requests += 1
    health_metrics.last_latency_ms = round(duration_ms, 2)
    if db_ok:
        health_metrics.successful_checks += 1
    else:
        health_metrics.failed_checks += 1

    # Emit structured log
    logger.info(
        "health_check_completed",
        database="ok" if db_ok else "unavailable",
        duration_ms=round(duration_ms, 2),
        timestamp=datetime.now(tz=UTC).isoformat(),
        status="healthy" if db_ok else "unhealthy",
    )

    status_code = 200 if db_ok else 503
    payload = {
        "status": "healthy" if db_ok else "unhealthy",
        "backend": "ok",
        "database": "ok" if db_ok else "unavailable",
    }
    return JSONResponse(status_code=status_code, content=payload)
