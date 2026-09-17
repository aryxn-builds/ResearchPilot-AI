from __future__ import annotations

import structlog
from langgraph.constants import Send

from app.core.config import settings
from app.graph.state import ResearchState

logger = structlog.get_logger(__name__)


def route_to_research(state: ResearchState) -> list[Send] | str:
    """Conditional edge: Fan-out to parallel research tasks."""
    plan = state.get("research_plan")
    sends = []

    if plan:
        for sq in plan.sub_questions:
            if sq.research_type == "web":
                sends.append(
                    Send(
                        "web_research", {"sub_question": sq, "session_id": state.get("session_id")}
                    )
                )

    if not sends:
        logger.warning("No web research required. Skipping to rank_sources.")
        return "rank_sources"

    return sends


def route_to_extraction(state: ResearchState) -> list[Send] | str:
    """Conditional edge: Fan-out to parallel evidence extraction tasks."""
    plan = state.get("research_plan")
    sources = state.get("sources", [])
    sends = []

    if plan and sources:
        # Cap sources per task to prevent context bloat (Rule E-01 / config constraints)
        top_sources = sources[: settings.RESEARCH_MAX_SOURCES_PER_TASK]

        for sq in plan.sub_questions:
            for source in top_sources:
                if not source.is_flagged:
                    sends.append(
                        Send(
                            "extract_evidence",
                            {
                                "sub_question": sq,
                                "source": source,
                                "session_id": state.get("session_id"),
                            },
                        )
                    )

    if not sends:
        logger.warning("No extraction tasks generated. Skipping to synthesize_claims.")
        return "synthesize_claims"

    return sends


def verify_claims_loop(state: ResearchState) -> str:
    """Conditional edge: Determine if we need another synthesis pass or can proceed to writing."""
    critic_result = state.get("critic_result")
    iterations = state.get("critic_iterations", 0)

    # Check if we've hit the hard cap limit (Rule A-06)
    if iterations >= settings.RESEARCH_MAX_ITERATIONS_HARD_CAP:
        logger.warning(
            "Critic loop reached hard cap limit", limit=settings.RESEARCH_MAX_ITERATIONS_HARD_CAP
        )
        return "write_report"

    if not critic_result:
        return "write_report"

    # Check if there are any unverified or contradicted claims
    needs_revision = any(
        c.verification_status in ("unverified", "contradicted") for c in critic_result.claims
    )

    if needs_revision:
        logger.info("Claims need revision. Routing back to synthesis.", iteration=iterations)
        return "synthesize_claims"

    return "write_report"
