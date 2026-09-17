from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SubQuestion(BaseModel):
    """A specific sub-question broken down from the main research question."""

    id: UUID = Field(..., description="Unique identifier for this sub-question")
    question: str = Field(..., description="The specific question to research")
    research_type: Literal["web", "academic", "rag"] = Field(
        ..., description="The type of research required for this question"
    )


class ResearchPlan(BaseModel):
    """The overall plan to answer a research question."""

    sub_questions: list[SubQuestion] = Field(..., description="List of sub-questions to research")


class Source(BaseModel):
    """A research source found during a research task."""

    id: UUID = Field(..., description="Unique identifier for this source")
    task_id: UUID | None = Field(
        default=None, description="ID of the task/sub-question this source answers"
    )
    url: str = Field(..., description="The URL or URI of the source")
    title: str = Field(..., description="The title of the source")
    content: str = Field(..., description="The extracted text content of the source")
    domain: str | None = Field(default=None, description="The domain of the source")
    published_date: str | None = Field(
        default=None, description="The publication date of the source"
    )
    credibility_score: float = Field(default=0.0, description="Heuristic score for credibility")
    relevance_score: float = Field(default=0.0, description="Heuristic score for relevance")
    is_flagged: bool = Field(default=False, description="Flagged for low credibility or quality")


class Evidence(BaseModel):
    """A specific snippet of evidence extracted from a source."""

    id: UUID = Field(..., description="Unique identifier for this evidence")
    sub_question_id: UUID = Field(..., description="ID of the sub-question this answers")
    source_id: UUID = Field(..., description="ID of the source this evidence came from")
    snippet: str = Field(..., description="Exact verbatim quote from the source content")


class Claim(BaseModel):
    """A factual claim generated from evidence."""

    id: UUID = Field(..., description="Unique identifier for this claim")
    statement: str = Field(..., description="The specific, falsifiable factual claim")
    evidence_ids: list[UUID] = Field(
        ..., description="IDs of the Evidence items supporting this claim"
    )
    verification_status: Literal["pending", "verified", "unverified", "contradicted"] = Field(
        default="pending", description="The verification status from the Critic Agent"
    )
    critic_notes: str | None = Field(default=None, description="Notes from the Critic Agent")


class CriticResult(BaseModel):
    """The result of the critic verification step."""

    claims: list[Claim] = Field(..., description="The claims with updated verification statuses")


class Report(BaseModel):
    """The final generated report."""

    markdown: str = Field(..., description="The full markdown report content with citations")
    citation_map: dict[str, str] = Field(
        ..., description="Map of citation markers (e.g., '[1]') to source UUIDs"
    )
    total_citations: int = Field(..., description="Count of unique cited sources")
    word_count: int = Field(..., description="Word count of the report")
    section_count: int = Field(..., description="Number of sections in the report")
