from __future__ import annotations

from uuid import uuid4

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.llm.router import LLMRouter
from app.prompts.synthesis import SYNTHESIS_SYSTEM_PROMPT
from app.schemas.agent import Claim, Evidence

logger = structlog.get_logger(__name__)


class SynthesisResult(BaseModel):
    claims: list[Claim]


class SynthesisAgent:
    """Agent responsible for synthesizing evidence into factual claims."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(
        self, evidence_list: list[Evidence], callbacks: list | None = None
    ) -> list[Claim]:
        """Synthesize a list of evidence into claims.

        Args:
            evidence_list: The extracted evidence items.
            callbacks: Optional LangChain callbacks.

        Returns:
            A list of synthesized Claims.
        """
        if not evidence_list:
            logger.info("No evidence to synthesize")
            return []

        logger.info("SynthesisAgent starting", num_evidence=len(evidence_list))

        # Prepare evidence JSON string
        evidence_data = [
            {
                "id": str(ev.id),
                "sub_question_id": str(ev.sub_question_id),
                "snippet": ev.snippet,
            }
            for ev in evidence_list
        ]

        import json

        human_content = (
            f"Evidence Items:\n<raw_source>\n{json.dumps(evidence_data, indent=2)}\n</raw_source>"
        )

        messages = [
            SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]

        result = await self.llm_router.generate_structured(
            messages, SynthesisResult, callbacks=callbacks
        )

        claims = result.claims
        for claim in claims:
            # Overwrite any LLM-hallucinated ID with a guaranteed unique UUID
            claim.id = str(uuid4())

        logger.info("SynthesisAgent completed", num_claims=len(claims))
        return claims
