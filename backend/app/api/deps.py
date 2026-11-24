"""Shared FastAPI dependencies.

Provides reusable Depends()-injectable functions for:
  - JWT authentication (get_current_user)
  - Service instances (get_research_service, get_user_service)

AGENTS.md Rule S-02: Every protected endpoint uses get_current_user.
AGENTS.md Rule AI-09: Services are injected, not instantiated in routes.
"""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthApiError, AuthRetryableError

from app.core.database import get_anon_client
from app.core.exceptions import AppError, InvalidTokenError, MissingAuthError
from app.core.security import AuthenticatedUser
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
                if isinstance(exc, AuthApiError) and exc.status < 500:
                    raise
                last_exc = exc
                if attempt < 2:
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
    except (AuthRetryableError, httpx.TransportError, TimeoutError) as exc:
        raise AppError("Sign-in verification is unavailable.", "AUTH_UNAVAILABLE", 503) from exc
    except AuthApiError as exc:
        if exc.status >= 500:
            raise AppError("Sign-in verification is unavailable.", "AUTH_UNAVAILABLE", 503) from exc
        raise InvalidTokenError() from exc
    except Exception as exc:
        raise InvalidTokenError() from exc


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
