"""Structured logging configuration.

Uses structlog for JSON-formatted, context-rich log output.
Log records always include: timestamp, level, logger, event.
When a request is in scope: request_id, method, path.
When a research session is in scope: session_id.

Never log API keys, tokens, passwords, or private user content.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog and stdlib logging for structured JSON output.

    Call once at application startup before any log messages are emitted.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR.
    """
    # Configure stdlib logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Determine renderer based on environment
    # Use ConsoleRenderer for development (human-readable), JSONRenderer for production
    renderer: structlog.types.Processor
    try:
        from app.core.config import settings

        use_json = settings.APP_ENV != "development"
    except Exception:
        use_json = False

    renderer = structlog.processors.JSONRenderer() if use_json else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named structlog logger.

    Args:
        name: Logger name, typically __name__.

    Returns:
        A structlog BoundLogger bound to the given name.

    Example:
        logger = get_logger(__name__)
        logger.info("research_started", session_id=session_id, question_length=len(question))
    """
    return structlog.get_logger(name)
