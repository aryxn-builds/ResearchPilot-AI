"""API v1 router — aggregates all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, research, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(research.router, prefix="/research", tags=["Research"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
