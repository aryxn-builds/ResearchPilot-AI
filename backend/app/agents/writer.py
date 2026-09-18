from __future__ import annotations

import json
import re
from typing import Any
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.router import LLMRouter
from app.prompts.writer import WRITER_SYSTEM_PROMPT
from app.schemas.agent import CitationEntry, Claim, Evidence, Report, Source

logger = structlog.get_logger(__name__)

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def build_citation_mappings(
    sources: list[Source], evidence_items: list[Evidence] | None = None
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Build authoritative citation maps from internal UUIDs to human-readable markers [1], [2].

    Returns:
        (source_id_to_marker, marker_to_source_id, evidence_id_to_source_id)
    """
    source_id_to_marker: dict[str, str] = {}
    marker_to_source_id: dict[str, str] = {}

    for i, s in enumerate(sources):
        marker = f"[{i + 1}]"
        s_id = str(s.id).lower()
        source_id_to_marker[s_id] = marker
        marker_to_source_id[marker] = s_id

    evidence_id_to_source_id: dict[str, str] = {}
    if evidence_items:
        for ev in evidence_items:
            evidence_id_to_source_id[str(ev.id).lower()] = str(ev.source_id).lower()

    return source_id_to_marker, marker_to_source_id, evidence_id_to_source_id


def sanitize_report(
    report: Report,
    sources: list[Source],
    evidence_items: list[Evidence] | None = None,
) -> Report:
    """Deterministically sanitize report markdown to ensure zero raw UUIDs leak into prose.

    Converts internal source/evidence UUIDs into human-readable citation markers [1], [2],
    strips malformed/orphaned UUID references, and updates the citation map.
    """
    source_id_to_marker, marker_to_source_id, evidence_id_to_source_id = build_citation_mappings(
        sources, evidence_items
    )

    markdown = report.markdown

    # 1. Handle bracketed expressions containing UUIDs: e.g. [f69cfed8-...] or [Source: f69c...]
    def replace_bracketed_uuids(match: re.Match) -> str:
        bracket_content = match.group(1)
        uuids = UUID_PATTERN.findall(bracket_content)
        if not uuids:
            return match.group(0)

        resolved_markers: list[str] = []
        for uid in uuids:
            uid_norm = uid.lower()
            if uid_norm in source_id_to_marker:
                m = source_id_to_marker[uid_norm]
                if m not in resolved_markers:
                    resolved_markers.append(m)
            elif uid_norm in evidence_id_to_source_id:
                src_id = evidence_id_to_source_id[uid_norm]
                if src_id in source_id_to_marker:
                    m = source_id_to_marker[src_id]
                    if m not in resolved_markers:
                        resolved_markers.append(m)

        # Retain any already-valid numeric markers in that same bracket
        for num_match in re.finditer(r"\b(\d+)\b", bracket_content):
            cand_marker = f"[{num_match.group(1)}]"
            if cand_marker in marker_to_source_id and cand_marker not in resolved_markers:
                resolved_markers.append(cand_marker)

        if resolved_markers:
            # Sort numerically
            nums = sorted(int(m.strip("[]")) for m in resolved_markers)
            return f"[{', '.join(str(n) for n in nums)}]"
        return ""

    # Replace bracketed citations with UUIDs
    sanitized = re.sub(r"\[([^\]]+)\]", replace_bracketed_uuids, markdown)

    # 2. Check for any bare UUIDs that might remain outside brackets
    def replace_bare_uuids(match: re.Match) -> str:
        uid_norm = match.group(0).lower()
        if uid_norm in source_id_to_marker:
            return source_id_to_marker[uid_norm]
        if uid_norm in evidence_id_to_source_id:
            src_id = evidence_id_to_source_id[uid_norm]
            if src_id in source_id_to_marker:
                return source_id_to_marker[src_id]
        return ""

    sanitized = UUID_PATTERN.sub(replace_bare_uuids, sanitized)

    # Clean up any leftover artifacts (e.g. spaces before punctuation)
    sanitized = re.sub(r" +([.,;:])", r"\1", sanitized)
    sanitized = re.sub(r" {2,}", " ", sanitized)

    # 3. Build authoritative citation_map based on markers present in sanitized markdown
    used_markers: set[str] = set()
    for match in re.finditer(r"\[(\d+(?:\s*,\s*\d+)*)\]", sanitized):
        for num_str in match.group(1).split(","):
            marker = f"[{num_str.strip()}]"
            if marker in marker_to_source_id:
                used_markers.add(marker)

    # Build sorted CitationEntry list
    sorted_markers = sorted(used_markers, key=lambda m: int(m.strip("[]")))
    citation_entries = [
        CitationEntry(marker=m, source_id=marker_to_source_id[m])
        for m in sorted_markers
    ]

    # If no markers were in prose but sources exist, map all available sources
    if not citation_entries and sources:
        citation_entries = [
            CitationEntry(marker=f"[{i + 1}]", source_id=str(s.id))
            for i, s in enumerate(sources)
        ]

    # Deterministic metrics
    words = len(re.findall(r"\b\w+\b", sanitized))
    sections = len(re.findall(r"^#{1,6}\s+", sanitized, re.MULTILINE))
    unique_sources_cited = len({entry.source_id for entry in citation_entries})

    return Report(
        markdown=sanitized,
        citation_map=citation_entries,
        total_citations=unique_sources_cited,
        word_count=words,
        section_count=sections,
    )


class WriterAgent:
    """Agent responsible for generating the final markdown report."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(
        self,
        research_question: str,
        verified_claims: list[Claim],
        sources: list[Source],
        evidence_items: list[Evidence] | None = None,
        callbacks: list | None = None,
    ) -> Report:
        """Write the final report based on verified claims and sources.

        Args:
            research_question: The original user question.
            verified_claims: Claims that passed the Critic Agent check.
            sources: The original sources for the bibliography.
            evidence_items: Optional extracted evidence items for claim traceability.
            callbacks: Optional LangChain callbacks.

        Returns:
            The generated and deterministically sanitized markdown Report.
        """
        if not verified_claims:
            logger.warning("No verified claims provided to WriterAgent")
            return Report(
                markdown="Insufficient verified information was found to answer the research question.",
                citation_map=[],
                total_citations=0,
                word_count=0,
                section_count=0,
            )

        logger.info("WriterAgent starting", num_verified_claims=len(verified_claims))

        # Build authoritative citation mappings
        source_id_to_marker, marker_to_source_id, evidence_id_to_source_id = build_citation_mappings(
            sources, evidence_items
        )

        # Prepare safe claim data: NO raw UUIDs passed to the LLM
        claims_data = []
        for c in verified_claims:
            claim_citations: list[str] = []
            for eid in c.evidence_ids:
                eid_norm = str(eid).lower()
                src_id = evidence_id_to_source_id.get(eid_norm)
                if src_id and src_id in source_id_to_marker:
                    marker = source_id_to_marker[src_id]
                    if marker not in claim_citations:
                        claim_citations.append(marker)
                elif eid_norm in source_id_to_marker:
                    marker = source_id_to_marker[eid_norm]
                    if marker not in claim_citations:
                        claim_citations.append(marker)

            claims_data.append(
                {
                    "statement": c.statement,
                    "citations": claim_citations,
                }
            )

        # Prepare safe source data: NO raw UUIDs passed to the LLM
        sources_data = [
            {
                "citation": source_id_to_marker[str(s.id).lower()],
                "title": s.title,
                "url": s.url,
            }
            for s in sources
        ]

        human_content = (
            f"Research Question: {research_question}\n\n"
            f"Verified Claims:\n<raw_source>\n{json.dumps(claims_data, indent=2)}\n</raw_source>\n\n"
            f"Available Sources:\n<raw_source>\n{json.dumps(sources_data, indent=2)}\n</raw_source>"
        )

        messages = [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]

        raw_report = await self.llm_router.generate_structured(
            messages, Report, callbacks=callbacks
        )

        # Deterministic sanitization pass
        final_report = sanitize_report(raw_report, sources, evidence_items)

        logger.info(
            "WriterAgent completed",
            total_citations=final_report.total_citations,
            word_count=final_report.word_count,
        )
        return final_report
