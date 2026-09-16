"""Database-layer models for research sessions and related records.

These TypedDicts represent the shape of rows returned from Supabase.
They are NOT Pydantic models — they are used only in the data layer.
API schemas (app/schemas/) are separate and must not be reused here.

AGENTS.md Rule AI-08: No duplicate utilities or models.
DATABASE_SCHEMA.md is the authority for column names and types.
"""

from __future__ import annotations


class ResearchSessionRow(dict):
    """TypedDict-compatible shape of a research_sessions table row.

    Columns match DATABASE_SCHEMA.md exactly.
    Used only in ResearchService for DB reads/writes.
    """

    # Not using TypedDict to avoid Python version complications;
    # this documents the expected shape from Supabase responses.
    #
    # Fields:
    #   id: UUID
    #   user_id: UUID
    #   research_question: str
    #   status: str  -- see ResearchStatus enum in schemas/research.py
    #   config: dict
    #   iteration_count: int
    #   total_claims: int | None
    #   verified_claims: int | None
    #   failure_reason: str | None
    #   started_at: str | None  -- ISO8601 from Supabase
    #   completed_at: str | None
    #   created_at: str
    #   updated_at: str
    #   deleted_at: str | None
    pass


class ReportRow(dict):
    """TypedDict-compatible shape of a reports table row.

    Fields:
      id: UUID
      session_id: UUID
      user_id: UUID
      content_markdown: str
      citation_map: dict
      total_citations: int
      word_count: int | None
      section_count: int | None
      generated_at: str
      created_at: str
      updated_at: str
    """

    pass
