"""Common API response schemas.

Implements the standard response envelope defined in API_SPEC.md:

  Success:   { "data": <T>, "meta": { "request_id": ..., "timestamp": ... } }
  Paginated: { "data": [...], "meta": { ..., "pagination": { ... } } }
  Error:     { "error": { "code": ..., "message": ..., "details": ... }, "meta": { ... } }

All route response_models must use these schemas.
Do not invent additional envelope fields not present in API_SPEC.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Standard response metadata included in every API response."""

    request_id: UUID = Field(
        default_factory=uuid4, description="Unique identifier for this request"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="UTC timestamp of the response",
    )


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(ge=1, le=50, description="Number of items per page")
    total: int = Field(ge=0, description="Total number of matching records")
    total_pages: int = Field(ge=0, description="Total number of pages")


class PaginatedResponseMeta(ResponseMeta):
    """Extended metadata for paginated list responses."""

    pagination: PaginationMeta


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response envelope.

    Example:
        return SuccessResponse(data=my_data)
    """

    data: T
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response envelope."""

    data: list[T]
    meta: PaginatedResponseMeta


class ErrorDetail(BaseModel):
    """The nested error object within an error response."""

    code: str = Field(description="Machine-readable error code (see API_SPEC.md)")
    message: str = Field(description="Human-readable error description")
    details: dict = Field(default_factory=dict, description="Optional additional context")


class ErrorResponse(BaseModel):
    """Standard error response envelope.

    Example:
        return ErrorResponse(
            error=ErrorDetail(code="RESEARCH_NOT_FOUND", message="...")
        )
    """

    error: ErrorDetail
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class AsyncJobResponse(BaseModel):
    """202 Accepted response for async job submissions (POST /api/v1/research)."""

    research_id: UUID
    status: str
    status_url: str
    stream_url: str


def make_success(data: T) -> SuccessResponse[T]:
    """Convenience factory for success responses."""
    return SuccessResponse(data=data)


def make_paginated(
    data: list[T],
    page: int,
    page_size: int,
    total: int,
) -> PaginatedResponse[T]:
    """Convenience factory for paginated responses."""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return PaginatedResponse(
        data=data,
        meta=PaginatedResponseMeta(
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            )
        ),
    )


def make_error(code: str, message: str, details: dict | None = None) -> ErrorResponse:
    """Convenience factory for error responses."""
    return ErrorResponse(error=ErrorDetail(code=code, message=message, details=details or {}))
