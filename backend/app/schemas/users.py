"""User API schemas.

Defines request/response Pydantic models for user profile endpoints.
Matches API_SPEC.md — do not add fields not in the spec.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """Authenticated user profile (GET /api/v1/users/me)."""

    id: UUID
    email: str
    display_name: str | None = None
    preferences: dict = Field(default_factory=dict)
    created_at: datetime


class UpdateUserRequest(BaseModel):
    """Request body for PATCH /api/v1/users/me.

    All fields are optional — only provided fields are updated.
    """

    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Display name shown in the UI",
    )
    preferences: dict | None = Field(
        default=None,
        description="User preferences object (merged with existing preferences)",
    )
