"""Research API schemas.

Defines request/response Pydantic models for all research-related endpoints.
All fields match API_SPEC.md exactly. Do not add fields not present in the spec.

Separate from database models — these are API contracts only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# ─────────────────────────────────────────────
# Status types (match DATABASE_SCHEMA.md enum)
# ─────────────────────────────────────────────

ResearchStatus = Literal[
    "pending",
    "planning",
    "researching",
    "verifying",
    "writing",
    "completed",
    "failed",
    "cancelled",
]

SourceType = Literal["web"]  # P1 adds "academic", "rag" — not in MVP scope


# ─────────────────────────────────────────────
# Request schemas
# ─────────────────────────────────────────────


class ResearchConfig(BaseModel):
    """Optional per-session research configuration (POST /api/v1/research).

    All fields are optional. Backend defaults apply when not provided.
    Source types are restricted to MVP-allowed values only.
    """

    max_iterations: int = Field(
        default=2, ge=1, le=3, description="Max critic retry iterations (1–3)"
    )
    source_types: list[SourceType] = Field(
        default_factory=lambda: ["web"],
        description="Source types to use. MVP supports 'web' only.",
    )
    max_sources_per_task: int = Field(
        default=5, ge=1, le=10, description="Maximum sources per research sub-task"
    )


class ResearchRequest(BaseModel):
    """Request body for POST /api/v1/research."""

    question: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="The research question to investigate (10–1,000 characters)",
    )
    config: ResearchConfig = Field(
        default_factory=ResearchConfig,
        description="Optional research configuration",
    )

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        """Ensure the question is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Research question must not be blank.")
        return stripped


# ─────────────────────────────────────────────
# Response schemas
# ─────────────────────────────────────────────


class ResearchSessionResponse(BaseModel):
    """Full research session detail (GET /api/v1/research/{id})."""

    id: UUID
    question: str
    status: ResearchStatus
    config: dict = Field(default_factory=dict)
    iteration_count: int = 0
    total_claims: int | None = None
    verified_claims: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    failure_reason: str | None = None


class ResearchListItem(BaseModel):
    """Abbreviated session data for history list (GET /api/v1/research)."""

    id: UUID
    question: str
    status: ResearchStatus
    verified_claims: int | None = None
    total_claims: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ResearchStatusResponse(BaseModel):
    """Lightweight status-only response (GET /api/v1/research/{id}/status)."""

    research_id: UUID
    status: ResearchStatus
    iteration_count: int = 0
    current_phase: str | None = None
    progress_pct: int = Field(default=0, ge=0, le=100)


class AsyncJobAccepted(BaseModel):
    """202 Accepted response data after submitting a research job."""

    research_id: UUID
    status: ResearchStatus = "pending"
    status_url: str
    stream_url: str


class CitationEntry(BaseModel):
    """A single citation in the report citation map."""

    source_id: UUID
    url: str
    title: str | None = None


class ReportSummary(BaseModel):
    """Summary statistics embedded in the report response."""

    total_claims: int
    verified_claims: int
    excluded_claims: int
    iterations: int


class ReportResponse(BaseModel):
    """Full report data (GET /api/v1/research/{id}/report?format=json)."""

    research_id: UUID
    generated_at: datetime
    content_markdown: str
    citation_map: dict[str, CitationEntry] = Field(
        default_factory=dict,
        description="Map of citation markers to source details, e.g. {'[1]': {...}}",
    )
    total_citations: int = 0
    word_count: int | None = None
    section_count: int | None = None
    summary: ReportSummary


class DeleteResearchResponse(BaseModel):
    """Response for DELETE /api/v1/research/{id}."""

    research_id: UUID
    status: ResearchStatus
