"""JWT validation utilities.

Validates Supabase-issued JWTs using the Supabase JWT secret (HS256).
Returns an AuthenticatedUser on success.
Raises MissingAuthError or InvalidTokenError on failure.

AGENTS.md Rule S-02: Every protected endpoint must validate the JWT.
AGENTS.md Rule S-01: The JWT secret never leaves the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt

from app.core.exceptions import InvalidTokenError, MissingAuthError


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents a successfully authenticated user extracted from a JWT.

    Attributes:
        id: The user's UUID (from the `sub` claim).
        email: The user's email address.
        role: The Supabase role claim (typically "authenticated").
    """

    id: UUID
    email: str
    role: str


def decode_supabase_jwt(token: str, jwt_secret: str) -> AuthenticatedUser:
    """Decode and validate a Supabase JWT.

    Args:
        token: Raw JWT string (without "Bearer " prefix).
        jwt_secret: The Supabase JWT secret from SUPABASE_JWT_SECRET.

    Returns:
        AuthenticatedUser with id, email, and role extracted from claims.

    Raises:
        MissingAuthError: If the token string is empty.
        InvalidTokenError: If the token is expired, malformed, or invalid.
    """
    if not token or not token.strip():
        raise MissingAuthError()

    try:
        payload: dict = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("The access token has expired.") from None
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError(f"Token validation failed: {exc}") from exc

    user_id_raw: str | None = payload.get("sub")
    email: str = payload.get("email", "")
    role: str = payload.get("role", "authenticated")

    if not user_id_raw:
        raise InvalidTokenError("Token is missing the 'sub' claim.")

    try:
        user_id = UUID(user_id_raw)
    except ValueError as exc:
        raise InvalidTokenError("Token 'sub' claim is not a valid UUID.") from exc

    return AuthenticatedUser(id=user_id, email=email, role=role)


def extract_bearer_token(authorization_header: str | None) -> str:
    """Extract the raw JWT from an Authorization: Bearer <token> header.

    Args:
        authorization_header: The full value of the Authorization header.

    Returns:
        The raw JWT string.

    Raises:
        MissingAuthError: If the header is absent.
        InvalidTokenError: If the header is malformed.
    """
    if not authorization_header:
        raise MissingAuthError()

    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":  # noqa: PLR2004
        raise InvalidTokenError("Authorization header must be in 'Bearer <token>' format.")

    return parts[1].strip()
