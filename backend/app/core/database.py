"""Supabase async client factory.

Two clients are configured:
- Anon client: uses SUPABASE_ANON_KEY, subject to RLS. Used for reading
  user-facing data where the user's JWT is forwarded.
- Service client: uses SUPABASE_SERVICE_ROLE_KEY, bypasses RLS. Used by
  agents and services for internal writes (claims, evidence, agent_runs).

ADR-003: Service Role is intentional; it must NEVER be exposed to the frontend.
AGENTS.md Rule AI-09: Always use the client from this module; never create new DB connections.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import AsyncClient, create_async_client

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_anon_client_sync() -> AsyncClient:
    """Internal: cached anon client constructor placeholder.

    Note: supabase-py's create_async_client is a coroutine, so we cannot
    use lru_cache directly on it. We instead cache the coroutine args
    and create the client in the lifespan context manager.
    """
    raise NotImplementedError("Use get_anon_client() from the lifespan-managed _clients dict.")


# Module-level client holders — populated during FastAPI lifespan startup.
_anon_client: AsyncClient | None = None
_service_client: AsyncClient | None = None


async def init_supabase_clients() -> None:
    """Initialize both Supabase async clients.

    Called once during FastAPI application startup (lifespan).
    After this call, get_anon_client() and get_service_client() are available.
    """
    global _anon_client, _service_client

    logger.info("Initializing Supabase clients")
    _anon_client = await create_async_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
    )
    _service_client = await create_async_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )
    logger.info("Supabase clients initialized", url=settings.SUPABASE_URL)


async def close_supabase_clients() -> None:
    """Close Supabase clients gracefully.

    Called during FastAPI application shutdown (lifespan).
    """
    global _anon_client, _service_client
    # supabase-py AsyncClient does not expose a .close() in all versions;
    # set to None to release references and let GC clean up.
    _anon_client = None
    _service_client = None
    logger.info("Supabase clients closed")


def get_anon_client() -> AsyncClient:
    """Return the Supabase anon client (RLS-enforced).

    Use for user-facing reads where the JWT is forwarded.
    Subject to Row-Level Security — users only see their own data.

    Returns:
        The initialized AsyncClient using the anon key.

    Raises:
        RuntimeError: If called before init_supabase_clients() has run.
    """
    if _anon_client is None:
        raise RuntimeError(
            "Supabase anon client is not initialized. Was init_supabase_clients() called?"
        )
    return _anon_client


def get_service_client() -> AsyncClient:
    """Return the Supabase service role client (RLS-bypassing).

    Use ONLY for internal backend writes (agent runs, evidence, claims).
    This client bypasses Row-Level Security — handle with care.
    NEVER pass this client to the frontend or expose the service role key.

    Returns:
        The initialized AsyncClient using the service role key.

    Raises:
        RuntimeError: If called before init_supabase_clients() has run.
    """
    if _service_client is None:
        raise RuntimeError(
            "Supabase service client is not initialized. Was init_supabase_clients() called?"
        )
    return _service_client
