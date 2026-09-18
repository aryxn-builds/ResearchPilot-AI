"""Shared FastAPI dependencies.

Provides reusable Depends()-injectable functions for:
  - JWT authentication (get_current_user)
  - Service instances (get_research_service, get_user_service)
  - SSE token validation (get_sse_user)

AGENTS.md Rule S-02: Every protected endpoint uses get_current_user.
AGENTS.md Rule AI-09: Services are injected, not instantiated in routes.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.exceptions import MissingAuthError, InvalidTokenError
from app.core.security import AuthenticatedUser
from app.core.database import get_anon_client
import asyncio
from app.services.research_service import ResearchService
from app.services.user_service import UserService

# HTTPBearer scheme — FastAPI will extract the Bearer token automatically
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthenticatedUser:
    """Validate the Bearer JWT and return the authenticated user.

    Inject with: user: Annotated[AuthenticatedUser, Depends(get_current_user)]

    Raises:
        MissingAuthError: If no Authorization header is present.
        InvalidTokenError: If the JWT is invalid or expired.
    """
    if credentials is None:
        raise MissingAuthError()

    token = credentials.credentials
    try:
        res = None
        last_exc = None
        for attempt in range(3):
            try:
                res = await get_anon_client().auth.get_user(token)
                break
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(1)
        if res is None:
            raise last_exc
        user = res.user
        if not user:
            raise InvalidTokenError("Token is missing user information.")
        return AuthenticatedUser(
            id=UUID(user.id),
            email=user.email or "",
            role=user.role or "authenticated"
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"DEBUG: get_current_user failed: {repr(exc)}")
        raise InvalidTokenError(f"Token validation failed: {exc}") from exc


async def get_sse_user(
    token: Annotated[str | None, Query(description="JWT for SSE authentication")] = None,
) -> AuthenticatedUser:
    """Validate a JWT provided as a query parameter for SSE connections.

    SSE does not support custom headers in all browsers, so the JWT is
    passed as ?token=<jwt>. The backend must NOT log this query parameter.

    See API_SPEC.md Security Note on SSE authentication.

    Raises:
        MissingAuthError: If no token query parameter is provided.
        InvalidTokenError: If the JWT is invalid or expired.
    """
    if not token:
        raise MissingAuthError("Token query parameter is required for SSE connections.")

    try:
        res = None
        last_exc = None
        for attempt in range(3):
            try:
                res = await get_anon_client().auth.get_user(token)
                break
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(1)
        if res is None:
            raise last_exc
        user = res.user
        if not user:
            raise InvalidTokenError("Token is missing user information.")
        return AuthenticatedUser(
            id=UUID(user.id),
            email=user.email or "",
            role=user.role or "authenticated"
        )
    except Exception as exc:
        print(f"DEBUG: get_sse_user failed: {exc}")
        raise InvalidTokenError(f"Token validation failed: {exc}") from exc


def get_research_service() -> ResearchService:
    """Return a ResearchService instance.

    Using a factory function (not a singleton) keeps the service stateless
    and testable — tests can override this dependency.
    """
    return ResearchService()


def get_user_service() -> UserService:
    """Return a UserService instance."""
    return UserService()


# Convenience type aliases for cleaner route signatures
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
SSEUser = Annotated[AuthenticatedUser, Depends(get_sse_user)]
