from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.llm.router import LLMRouter
from app.prompts.critic import CRITIC_SYSTEM_PROMPT
from app.schemas.agent import Claim, CriticResult, Evidence

logger = structlog.get_logger(__name__)


class CriticAgent:
    """Agent responsible for verifying claims against evidence."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(self, claims: list[Claim], evidence_list: list[Evidence]) -> CriticResult:
        """Verify the synthesized claims.
        
        Args:
            claims: The synthesized claims to verify.
            evidence_list: The original extracted evidence items.
            
        Returns:
            The CriticResult containing verified/unverified/contradicted statuses.
        """
        if not claims:
            logger.info("No claims to verify")
            return CriticResult(claims=[])

        logger.info("CriticAgent starting", num_claims=len(claims))
        
        # Prepare inputs
        claims_data = [
            {
                "id": str(c.id),
                "statement": c.statement,
                "evidence_ids": [str(eid) for eid in c.evidence_ids],
            }
            for c in claims
        ]
        
        evidence_data = [
            {
                "id": str(ev.id),
                "snippet": ev.snippet,
            }
            for ev in evidence_list
        ]
        
        human_content = (
            f"Evidence Items:\n{evidence_data}\n\n"
            f"Claims to Verify:\n{claims_data}"
        )
        
        messages = [
            SystemMessage(content=CRITIC_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        
        result = await self.llm_router.generate_structured(messages, CriticResult)
        
        logger.info("CriticAgent completed")
        return result
