from __future__ import annotations

from typing import Annotated, TypedDict

from app.schemas.agent import Claim, CriticResult, Evidence, Report, ResearchPlan, Source


def merge_list_or_overwrite(existing: list, new: list | dict) -> list:
    """Reducer that appends by default, or overwrites if dict with 'overwrite' is passed."""
    if isinstance(new, dict) and new.get("overwrite"):
        return new.get("items", [])
    if isinstance(new, list):
        return existing + new
    return existing


class ResearchState(TypedDict):
    """The state object passed through the LangGraph pipeline."""

    # ─────────────────────────────────────────────
    # INPUT STATE
    # ─────────────────────────────────────────────

    # Session ID for persistence mapping
    session_id: str

    # The original question provided by the user
    research_question: str

    # ─────────────────────────────────────────────
    # PIPELINE STATE
    # ─────────────────────────────────────────────

    # Step 1: Planner output
    research_plan: ResearchPlan | None

    # Step 2: Web Research & Ranking output
    sources: Annotated[list[Source], merge_list_or_overwrite]

    # Step 3: Evidence Extraction output
    evidence_items: Annotated[list[Evidence], merge_list_or_overwrite]

    # Step 4: Synthesis output (overwrites previous state on retry loops)
    claims: list[Claim]

    # Step 5: Critic output (overwrites previous state)
    critic_result: CriticResult | None

    # Loop Counter for Critic feedback cycle (Rule A-06)
    critic_iterations: int

    # ─────────────────────────────────────────────
    # OUTPUT STATE
    # ─────────────────────────────────────────────

    # Step 6: Final report
    report: Report | None
