from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.llm.router import LLMRouter
from app.prompts.planner import PLANNER_SYSTEM_PROMPT
from app.schemas.agent import ResearchPlan

logger = structlog.get_logger(__name__)


class PlannerAgent:
    """Agent responsible for decomposing research questions into a plan."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(self, research_question: str, callbacks: list | None = None) -> ResearchPlan:
        """Decompose a question into a ResearchPlan.

        Args:
            research_question: The main question from the user.
            callbacks: Optional LangChain callbacks.

        Returns:
            A ResearchPlan containing SubQuestions.
        """
        logger.info("PlannerAgent starting", question=research_question)

        system_prompt = PLANNER_SYSTEM_PROMPT.format(
            max_questions=settings.RESEARCH_MAX_SUB_QUESTIONS
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Research Question: {research_question}"),
        ]

        # Will raise ProviderExhaustedError if all providers fail
        plan: ResearchPlan = await self.llm_router.generate_structured(
            messages, ResearchPlan, callbacks=callbacks
        )

        import uuid
        for sq in plan.sub_questions:
            sq.id = uuid.uuid4()

        logger.info("PlannerAgent completed", num_sub_questions=len(plan.sub_questions))
        return plan
