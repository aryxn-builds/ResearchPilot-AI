"""Health check endpoints.

GET /api/v1/health     — Liveness probe (always returns 200 if server is up)
GET /api/v1/readiness  — Readiness probe (checks Supabase connectivity)

These endpoints are excluded from rate limiting and auth requirements.
They are excluded from access logs to reduce noise (see middleware/logging.py).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
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
