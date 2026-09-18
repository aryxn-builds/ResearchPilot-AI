from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.llm.router import LLMRouter
from app.prompts.extractor import EXTRACTOR_SYSTEM_PROMPT
from app.schemas.agent import Evidence, Source, SubQuestion

logger = structlog.get_logger(__name__)


class LLMEvidenceItem(BaseModel):
    """A simplified representation of extracted evidence for the LLM to generate."""
    snippet: str = Field(description="Exact verbatim quote from the source content")


class ExtractionResult(BaseModel):
    """Wrapper for the LLM output."""

    evidence_items: list[LLMEvidenceItem]


class EvidenceExtractor:
    """Agent responsible for extracting specific evidence snippets from sources."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(
        self, sub_question: SubQuestion, source: Source, callbacks: list | None = None
    ) -> list[Evidence]:
        """Extract evidence from a source to answer a sub-question.

        Args:
            sub_question: The SubQuestion being researched.
            source: The gathered source (with content/snippet).
            callbacks: Optional LangChain callbacks.

        Returns:
            A list of Evidence models.
        """
        logger.info(
            "EvidenceExtractor starting", question_id=str(sub_question.id), source_id=str(source.id)
        )

        if not source.content:
            logger.warning("Source has no content", source_id=str(source.id))
            return []

        human_content = (
            f"Sub-Question ID: {sub_question.id}\n"
            f"Question: {sub_question.question}\n\n"
            f"Source ID: {source.id}\n"
            f"Source URL: {source.url}\n"
            f"Source Content:\n<raw_source>\n{source.content}\n</raw_source>\n"
        )

        messages = [
            SystemMessage(content=EXTRACTOR_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]

        try:
            result = await self.llm_router.generate_structured(
                messages, ExtractionResult, callbacks=callbacks
            )

            # Map back to domain model
            evidence_list = []
            for item in result.evidence_items:
                import uuid
                evidence = Evidence(
                    id=str(uuid.uuid4()),
                    sub_question_id=sub_question.id,
                    source_id=source.id,
                    snippet=item.snippet,
                )
                evidence_list.append(evidence)

            logger.info("Evidence extraction complete", extracted_count=len(evidence_list))
            return evidence_list

        except Exception as e:
            logger.error("Evidence extraction failed", error=str(e), source_id=str(source.id))
            return []
