from __future__ import annotations

import uuid

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.research_mode import fast_research
from app.llm.router import LLMRouter
from app.prompts.extractor import EXTRACTOR_SYSTEM_PROMPT
from app.schemas.agent import Evidence, Source, SubQuestion

logger = structlog.get_logger(__name__)


class LLMEvidenceItem(BaseModel):
    """A simplified representation of extracted evidence for the LLM to generate."""

    source_id: str = Field(description="The exact Source ID from which this snippet was verbatim extracted")
    snippet: str = Field(description="Exact verbatim quote from the source content")


class ExtractionResult(BaseModel):
    """Wrapper for the LLM output."""

    evidence_items: list[LLMEvidenceItem]


class EvidenceExtractor:
    """Agent responsible for extracting specific evidence snippets from sources.

    Supports both single-source and batched multi-source extraction to reduce LLM roundtrips
    while strictly preserving source attribution and claim-to-evidence provenance.
    """

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run_batch(
        self, sub_question: SubQuestion, sources: list[Source], callbacks: list | None = None
    ) -> list[Evidence]:
        """Extract evidence from a batch of sources to answer a sub-question.

        Args:
            sub_question: The SubQuestion being researched.
            sources: List of gathered sources for this sub-question task.
            callbacks: Optional LangChain callbacks.

        Returns:
            A list of Evidence domain models with authoritative UUIDs.
        """
        valid_sources = [s for s in sources if s.content and s.content.strip()]
        if not valid_sources:
            logger.warning("No valid source content for extraction batch", question_id=str(sub_question.id))
            return []

        logger.info(
            "EvidenceExtractor starting batch",
            question_id=str(sub_question.id),
            batch_size=len(valid_sources),
            source_ids=[str(s.id) for s in valid_sources],
        )

        fast = fast_research.get()
        max_chars = settings.FAST_SOURCE_CHARS if fast else settings.RESEARCH_MAX_SOURCE_CONTENT_TOKENS * 4
        shown_content: dict[str, str] = {}
        source_sections = []
        for s in valid_sources:
            content = s.content[:max_chars] if len(s.content) > max_chars else s.content
            shown_content[str(s.id)] = content
            source_sections.append(
                f'<source id="{s.id}" url="{s.url}">\n<raw_source>\n{content}\n</raw_source>\n</source>'
            )

        human_content = (
            f"Sub-Question ID: {sub_question.id}\n"
            f"Sub-Question: {sub_question.question}\n\n"
            f"Please extract factual, verbatim evidence snippets from the provided sources that directly answer the sub-question.\n"
            f"For each snippet extracted, specify the exact source_id matching the <source id=\"...\"> tag.\n\n"
            + ("Return at most two short verbatim passages per source.\n" if fast else "")
            + "Sources:\n" + "\n\n".join(source_sections)
        )

        messages = [
            SystemMessage(content=EXTRACTOR_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]

        try:
            result = await self.llm_router.generate_structured(
                messages, ExtractionResult, callbacks=callbacks
            )

            valid_source_map = {str(s.id): s for s in valid_sources}
            evidence_list: list[Evidence] = []

            seen: set[tuple[str, str]] = set()
            for item in result.evidence_items:
                sid = str(item.source_id).strip()
                if sid not in valid_source_map:
                    # Fallback: if single source in batch, safely attribute to it
                    if len(valid_sources) == 1 and not fast:
                        sid = str(valid_sources[0].id)
                    else:
                        logger.warning(
                            "Dropping evidence item with unmapped source_id",
                            invalid_source_id=sid,
                            valid_ids=list(valid_source_map.keys()),
                        )
                        continue

                if fast:
                    snippet = " ".join(item.snippet.split())
                    if (not snippet or (sid, snippet) in seen
                            or snippet not in " ".join(shown_content[sid].split())):
                        continue
                    seen.add((sid, snippet))
                    if len(evidence_list) >= settings.FAST_MAX_EVIDENCE:
                        break

                # Generate deterministic authoritative domain ID
                ev_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{sub_question.id}:{sid}:{item.snippet}"))
                evidence = Evidence(
                    id=ev_id,
                    sub_question_id=sub_question.id,
                    source_id=sid,
                    snippet=item.snippet,
                )
                evidence_list.append(evidence)

            logger.info("Evidence batch extraction complete", extracted_count=len(evidence_list))
            return evidence_list

        except Exception as e:
            logger.error("Evidence batch extraction failed", error=str(e), question_id=str(sub_question.id))
            return []

    async def run(
        self, sub_question: SubQuestion, source: Source, callbacks: list | None = None
    ) -> list[Evidence]:
        """Extract evidence from a single source (backward compatibility)."""
        return await self.run_batch(sub_question, [source], callbacks=callbacks)
