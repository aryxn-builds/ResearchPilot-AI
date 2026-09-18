"""FastAPI application factory and entry point.

Creates, configures, and returns the FastAPI application instance.
All middleware, exception handlers, and routers are registered here.

This module must not contain business logic.
Start the server with:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_supabase_clients, init_supabase_clients
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

# Configure logging before anything else
configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


# ─────────────────────────────────────────────
# Lifespan — startup / shutdown hooks
# ─────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle.

    Startup: Initialize Supabase clients.
    Shutdown: Close Supabase clients gracefully.
    """
    logger.info(
        "application_starting",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )

    await init_supabase_clients()

    logger.info("application_ready")
    yield

    logger.info("application_shutting_down")
    await close_supabase_clients()
    logger.info("application_shutdown_complete")


# ─────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Fully configured FastAPI instance ready to serve.
    """
    app = FastAPI(
        title="ResearchPilot AI API",
        description=(
            "Autonomous multi-agent research and report-generation platform. "
            "Accepts complex research questions and produces evidence-backed, "
            "cited reports using a multi-agent LangGraph pipeline."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost first) ──────────────────────────
    # CORS must be before other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX if settings.CORS_ORIGIN_REGEX.strip() else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID + structured logging
    app.add_middleware(RequestLoggingMiddleware)

    # Per-user rate limiting (in-memory, MVP — see ADR-002)
    app.add_middleware(RateLimitMiddleware)

    # ── Exception handlers ───────────────────────────────────────────────────
    _register_exception_handlers(app)

    # ── Routers ─────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    Converts all AppError subclasses and FastAPI validation errors
    to the standard API error envelope defined in API_SPEC.md.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle all AppError subclasses (auth, not found, rate limit, etc.)."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(
            "handled_app_error",
            error_code=exc.code,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "meta": {"request_id": request_id},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI/Pydantic request body validation errors (422)."""
        request_id = getattr(request.state, "request_id", "unknown")
        # Flatten validation error details for client readability
        details = [
            {
                "field": " → ".join(str(loc) for loc in error["loc"] if loc != "body"),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": {"errors": details},
                },
                "meta": {"request_id": request_id},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unexpected errors. Never expose stack traces to clients."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal server error occurred.",
                    "details": {},
                },
                "meta": {"request_id": request_id},
            },
        )


# ─────────────────────────────────────────────
# Application instance (used by uvicorn)
# ─────────────────────────────────────────────

app = create_app()
