from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.schemas.agent import Claim, CriticResult, Evidence, ResearchPlan, Source


class ResearchState(TypedDict):
    """The state object passed through the LangGraph pipeline."""

    # ─────────────────────────────────────────────
    # INPUT STATE
    # ─────────────────────────────────────────────
    
    # The original question provided by the user
    research_question: str
    
    # ─────────────────────────────────────────────
    # PIPELINE STATE
    # ─────────────────────────────────────────────
    
    # Step 1: Planner output
    research_plan: ResearchPlan | None
    
    # Step 2: Web Research & Ranking output
    # Uses `operator.add` to allow parallel fan-out steps to append to the list
    sources: Annotated[list[Source], operator.add]
    
    # Step 3: Evidence Extraction output
    evidence_items: Annotated[list[Evidence], operator.add]
    
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
    report_markdown: str | None
