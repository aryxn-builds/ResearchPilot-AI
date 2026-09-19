# V1 Specification Freeze

> **Status:** Specification Frozen
> **Version:** 1.0.0 (Docs)
> **Date:** 2026-09-16

This document formally marks the transition from Phase 0 (Planning/Architecture) to Phase 1 (MVP Implementation) for ResearchPilot AI.

## Scope of V1 (MVP)

The following core features are locked in for the MVP (Phase 1) implementation:

1.  **Core Research Flow:** User submits question -> Planner -> Web Research -> Ranking -> Extraction -> Synthesis -> Critic -> Report.
2.  **LLM Router Abstraction:** Gemini as primary, Groq and OpenRouter as fallbacks.
3.  **Authentication & Database:** Supabase Auth (email/password) and PostgreSQL via Supabase client.
4.  **UI/UX:** "Sage Intelligence" aesthetic (neutral-first, calm, professional) implemented via Next.js App Router and Tailwind CSS.
5.  **Streaming:** Real-time Server-Sent Events (SSE) from FastAPI to Next.js for agent progress.

## Excluded from V1 (P1+ Features)

The following features are strictly excluded from the MVP scope and must NOT be implemented during Phase 1:

1.  Academic research (Semantic Scholar, arXiv).
2.  Private document uploads & Vector DB (RAG, Qdrant).
3.  PDF Report Export.
4.  User-configurable research parameters (depth, custom source types).
5.  Agent activity transparency panel.

## Documentation Versions Frozen

All core documents have been audited for consistency and frozen at Version 1.0.0:

-   `PRD.md`
-   `ARCHITECTURE.md`
-   `AGENTS.md`
-   `DATABASE_SCHEMA.md`
-   `API_SPEC.md`
-   `DESIGN_SYSTEM.md`
-   `UI_UX_SPEC.md`
-   `USER_FLOWS.md`

## Next Phase Protocol

All agents working on Phase 1 MUST adhere strictly to `AGENTS.md`. No new dependencies, architectural patterns, or database changes may be introduced without first unfreezing and updating the relevant specification document via an approved Pull Request.
