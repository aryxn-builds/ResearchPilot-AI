"""User profile API endpoints.

GET   /api/v1/users/me  — Fetch authenticated user's profile
PATCH /api/v1/users/me  — Update display_name and/or preferences
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_user_service
from app.schemas.common import SuccessResponse, make_success
from app.schemas.users import UpdateUserRequest, UserResponse
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "/me",
    summary="Get current user profile",
    description="Returns the authenticated user's profile data.",
    response_model=SuccessResponse[UserResponse],
)
async def get_me(
    user: CurrentUser,
    service: UserService = Depends(get_user_service),
) -> SuccessResponse[UserResponse]:
    """Fetch the authenticated user's profile."""
    profile = await service.get_user(user_id=user.id)
    return make_success(profile)


@router.patch(
    "/me",
    summary="Update user profile",
    description="Update mutable profile fields. All fields are optional; only provided fields are updated.",
    response_model=SuccessResponse[UserResponse],
)
async def update_me(
    body: UpdateUserRequest,
    user: CurrentUser,
    service: UserService = Depends(get_user_service),
) -> SuccessResponse[UserResponse]:
    """Update the authenticated user's profile."""
    updated = await service.update_user(user_id=user.id, request=body)
    return make_success(updated)
