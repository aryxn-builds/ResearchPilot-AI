"""Observability module — safe, non-blocking Langfuse integration.

Ensures that:
1. Langfuse tracing is enabled only when validly configured.
2. Failure or unavailability of Langfuse NEVER crashes or blocks research execution.
3. Diagnostic checks test connectivity without exposing secrets.
4. Database agent_runs telemetry persists independently.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_langfuse_health_cache: dict[str, Any] | None = None


def check_langfuse_health(force_refresh: bool = False) -> dict[str, Any]:
    """Check Langfuse configuration and connectivity without exposing secrets.

    Returns:
        Dict with 'status' in ('disabled', 'unconfigured', 'healthy', 'unauthorized', 'error')
        and human-readable 'message'.
    """
    global _langfuse_health_cache
    if _langfuse_health_cache is not None and not force_refresh:
        return _langfuse_health_cache

    if not settings.LANGFUSE_ENABLED:
        result = {"status": "disabled", "message": "Langfuse tracing is disabled in settings."}
        _langfuse_health_cache = result
        return result

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        result = {"status": "unconfigured", "message": "Langfuse public/secret keys are not configured."}
        _langfuse_health_cache = result
        return result

    # Ensure environment variables match settings for Langfuse SDK
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        auth_ok = client.auth_check()
        if auth_ok:
            result = {
                "status": "healthy",
                "host": settings.LANGFUSE_HOST,
                "message": "Langfuse authenticated successfully and ready for tracing.",
            }
        else:
            result = {
                "status": "unauthorized",
                "host": settings.LANGFUSE_HOST,
                "message": "Langfuse authentication rejected: invalid credentials or host.",
            }
    except Exception as e:
        err_msg = str(e)
        if "unauthorized" in err_msg.lower() or "401" in err_msg or "Invalid credentials" in err_msg:
            result = {
                "status": "unauthorized",
                "host": settings.LANGFUSE_HOST,
                "message": "Langfuse authentication rejected (401 Unauthorized / Invalid credentials).",
            }
        else:
            result = {
                "status": "error",
                "host": settings.LANGFUSE_HOST,
                "message": f"Langfuse connection error: {err_msg}",
            }

    _langfuse_health_cache = result
    return result


def get_langfuse_callback(session_id: str | None = None) -> list:
    """Return Langchain CallbackHandler for Langfuse if healthy and configured.

    Returns:
        List containing CallbackHandler if ready, otherwise empty list.
        NEVER raises an exception.
    """
    health = check_langfuse_health()
    if health.get("status") != "healthy":
        return []

    try:
        from langfuse.langchain import CallbackHandler

        trace_ctx = {"trace_id": str(session_id)} if session_id else None
        handler = CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            trace_context=trace_ctx,
        )
        return [handler]
    except Exception as e:
        logger.warning("langfuse_callback_creation_failed", error=str(e))
        return []
