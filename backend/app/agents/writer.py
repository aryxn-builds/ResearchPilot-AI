from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.router import LLMRouter
from app.prompts.writer import WRITER_SYSTEM_PROMPT
from app.schemas.agent import Claim, Report, Source

logger = structlog.get_logger(__name__)


class WriterAgent:
    """Agent responsible for generating the final markdown report."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(
        self, research_question: str, verified_claims: list[Claim], sources: list[Source]
    ) -> Report:
        """Write the final report based on verified claims and sources.
        
        Args:
            research_question: The original user question.
            verified_claims: Claims that passed the Critic Agent check.
            sources: The original sources for the bibliography.
            
        Returns:
            The generated markdown Report.
        """
        if not verified_claims:
            logger.warning("No verified claims provided to WriterAgent")
            return Report(
                markdown="Insufficient verified information was found to answer the research question."
            )

        logger.info("WriterAgent starting", num_verified_claims=len(verified_claims))
        
        claims_data = [
            {
                "statement": c.statement,
                "evidence_ids": [str(eid) for eid in c.evidence_ids],
            }
            for c in verified_claims
        ]
        
        sources_data = [
            {
                "id": str(s.id),
                "title": s.title,
                "url": s.url,
            }
            for s in sources
        ]
        
        human_content = (
            f"Research Question: {research_question}\n\n"
            f"Verified Claims:\n{claims_data}\n\n"
            f"Available Sources:\n{sources_data}"
        )
        
        messages = [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        
        result = await self.llm_router.generate_structured(messages, Report)
        
        logger.info("WriterAgent completed")
        return result
