from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.llm.router import LLMRouter
from app.prompts.extractor import EXTRACTOR_SYSTEM_PROMPT
from app.schemas.agent import Evidence, Source, SubQuestion
from uuid import uuid4

logger = structlog.get_logger(__name__)


class ExtractionResult(BaseModel):
    """Wrapper for the LLM output."""
    evidence_items: list[Evidence]


class EvidenceExtractor:
    """Agent responsible for extracting specific evidence snippets from sources."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(self, sub_question: SubQuestion, source: Source) -> list[Evidence]:
        """Extract evidence from a single source for a single sub-question.
        
        Args:
            sub_question: The question to answer.
            source: The source to extract from.
            
        Returns:
            A list of Evidence items.
        """
        if source.is_flagged:
            logger.info("Skipping flagged source", source_id=str(source.id))
            return []

        logger.info("EvidenceExtractor starting", source_id=str(source.id), question_id=str(sub_question.id))
        
        human_content = (
            f"Sub-Question ID: {sub_question.id}\n"
            f"Question: {sub_question.question}\n\n"
            f"Source ID: {source.id}\n"
            f"Source URL: {source.url}\n"
            f"Source Content:\n{source.content}\n"
        )
        
        messages = [
            SystemMessage(content=EXTRACTOR_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        
        try:
            result = await self.llm_router.generate_structured(messages, ExtractionResult)
            
            # Ensure IDs match the inputs, as the LLM might hallucinate them
            validated_evidence = []
            for item in result.evidence_items:
                item.id = uuid4()
                item.sub_question_id = sub_question.id
                item.source_id = source.id
                validated_evidence.append(item)
                
            logger.info("EvidenceExtractor completed", num_evidence=len(validated_evidence))
            return validated_evidence
            
        except Exception as e:
            logger.error("Evidence extraction failed", error=str(e), source_id=str(source.id))
            return []
