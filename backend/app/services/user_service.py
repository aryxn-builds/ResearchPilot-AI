"""UserService — user profile operations via Supabase.

Responsibilities:
  - Fetch user profile from the `users` table.
  - Update mutable user fields (display_name, preferences).

AGENTS.md Rule A-01: Business logic lives here, not in route handlers.
AGENTS.md Rule S-03: All queries include user_id filter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from app.core.database import get_service_client
from app.core.exceptions import NotFoundError
from app.schemas.users import UpdateUserRequest, UserResponse

logger = structlog.get_logger(__name__)


class UserService:
    """Manages user profile read/write operations."""

    async def get_user(self, user_id: UUID) -> UserResponse:
        """Fetch the user's profile from the database.

        Args:
            user_id: The authenticated user's UUID.

        Returns:
            UserResponse with profile data.

        Raises:
            NotFoundError: If the user record does not exist.
        """
        client = get_service_client()
        result = await client.table("users").select("*").eq("id", str(user_id)).execute()
        if not result.data:
            raise NotFoundError("User profile not found.")

        row = result.data[0]
        return UserResponse(
            id=UUID(row["id"]),
            email=row["email"],
            display_name=row.get("display_name"),
            preferences=row.get("preferences") or {},
            created_at=row["created_at"],
        )

    async def update_user(self, user_id: UUID, request: UpdateUserRequest) -> UserResponse:
        """Update mutable user profile fields.

        Args:
            user_id: The authenticated user's UUID.
            request: Fields to update (all optional).

        Returns:
            Updated UserResponse.

        Raises:
            NotFoundError: If the user record does not exist.
        """
        client = get_service_client()
        update_data: dict = {"updated_at": datetime.now(tz=UTC).isoformat()}

        if request.display_name is not None:
            update_data["display_name"] = request.display_name

        if request.preferences is not None:
            # Merge with existing preferences rather than replace
            existing = await self.get_user(user_id)
            merged = {**existing.preferences, **request.preferences}
            update_data["preferences"] = merged

        result = await client.table("users").update(update_data).eq("id", str(user_id)).execute()
        if not result.data:
            raise NotFoundError("User profile not found.")

        row = result.data[0]
        return UserResponse(
            id=UUID(row["id"]),
            email=row["email"],
            display_name=row.get("display_name"),
            preferences=row.get("preferences") or {},
            created_at=row["created_at"],
        )
