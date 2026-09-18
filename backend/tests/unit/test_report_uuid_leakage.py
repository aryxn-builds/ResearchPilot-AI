import re
import pytest
from pydantic import BaseModel

from app.agents.writer import WriterAgent, sanitize_report
from app.schemas.agent import CitationEntry, Claim, Evidence, Report, Source

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class MockLLMRouter:
    def __init__(self, mock_report: Report):
        self.mock_report = mock_report
        self.last_messages = None

    async def generate_structured(self, messages, response_schema, **kwargs):
        self.last_messages = messages
        return self.mock_report


@pytest.mark.asyncio
async def test_writer_prompt_does_not_contain_raw_uuids():
    """Verify that WriterAgent constructs safe prompts without leaking raw UUIDs to the LLM."""
    source_uuid = "f69cfed8-bc72-56e6-9f9c-fec10346428d"
    evidence_uuid = "a1111111-2222-3333-4444-555555555555"
    claim_uuid = "c2222222-3333-4444-5555-666666666666"

    sources = [
        Source(
            id=source_uuid,
            title="Quantum Advantage Report",
            url="https://example.com/quantum",
            content="Quantum processors achieve exponential speedups.",
        )
    ]
    evidence = [
        Evidence(
            id=evidence_uuid,
            sub_question_id="sq-1",
            source_id=source_uuid,
            snippet="Quantum processors achieve exponential speedups.",
        )
    ]
    claims = [
        Claim(
            id=claim_uuid,
            statement="Quantum computing delivers exponential computational advantages.",
            evidence_ids=[evidence_uuid],
            verification_status="verified",
        )
    ]

    mock_report = Report(
        markdown="# Research on Quantum Computing\n\nQuantum processors achieve speedups [1].\n\n## References\n[1] Quantum Advantage Report - https://example.com/quantum",
        citation_map=[CitationEntry(marker="[1]", source_id=source_uuid)],
        total_citations=1,
        word_count=20,
        section_count=2,
    )

    router = MockLLMRouter(mock_report)
    agent = WriterAgent(llm_router=router)

    report = await agent.run(
        research_question="What are the advantages of quantum computing?",
        verified_claims=claims,
        sources=sources,
        evidence_items=evidence,
    )

    # Inspect the message sent to LLM
    assert router.last_messages is not None
    human_msg = router.last_messages[1].content

    # The prompt should NOT contain the raw source or evidence UUIDs
    assert source_uuid not in human_msg, "Raw source UUID leaked into Writer prompt"
    assert evidence_uuid not in human_msg, "Raw evidence UUID leaked into Writer prompt"
    assert "[1]" in human_msg, "Human-readable citation marker [1] should be in prompt"

    # Final report must have no raw UUIDs
    assert UUID_PATTERN.search(report.markdown) is None
    assert "[1]" in report.markdown


def test_sanitize_report_replaces_bracketed_source_uuid():
    """Regression test: input containing [f69cfed8-bc72-56e6-9f9c-fec10346428d] must be mapped to [1]."""
    source_uuid = "f69cfed8-bc72-56e6-9f9c-fec10346428d"
    sources = [
        Source(
            id=source_uuid,
            title="AI Safety and Alignment",
            url="https://example.com/safety",
            content="Safety verification is critical.",
        )
    ]

    raw_markdown = (
        "# AI Safety\n\n"
        "Reinforcement learning requires strict guardrails [f69cfed8-bc72-56e6-9f9c-fec10346428d].\n\n"
        "## References\n"
        "[f69cfed8-bc72-56e6-9f9c-fec10346428d] AI Safety and Alignment"
    )

    raw_report = Report(
        markdown=raw_markdown,
        citation_map=[],
        total_citations=0,
        word_count=15,
        section_count=2,
    )

    sanitized = sanitize_report(raw_report, sources=sources)

    # 1. No raw UUIDs in report markdown
    assert UUID_PATTERN.search(sanitized.markdown) is None, "Raw UUID leaked into sanitized report markdown"

    # 2. Citation marker [1] remains present
    assert "[1]" in sanitized.markdown

    # 3. Source mapping is valid in citation_map
    assert len(sanitized.citation_map) == 1
    assert sanitized.citation_map[0].marker == "[1]"
    assert sanitized.citation_map[0].source_id == source_uuid

    # 4. Total citations count updated
    assert sanitized.total_citations == 1


def test_sanitize_report_resolves_evidence_uuid():
    """Evidence UUIDs appearing inside brackets must resolve to their source's citation marker."""
    source_uuid = "11111111-2222-3333-4444-555555555555"
    evidence_uuid = "99999999-8888-7777-6666-555555555555"

    sources = [
        Source(
            id=source_uuid,
            title="Autonomous Systems",
            url="https://example.com/auto",
            content="Autonomous agents execute multi-step workflows.",
        )
    ]
    evidence = [
        Evidence(
            id=evidence_uuid,
            sub_question_id="sq-1",
            source_id=source_uuid,
            snippet="Autonomous agents execute multi-step workflows.",
        )
    ]

    raw_markdown = f"Agents operate autonomously [{evidence_uuid}]."
    raw_report = Report(
        markdown=raw_markdown,
        citation_map=[],
        total_citations=0,
        word_count=5,
        section_count=0,
    )

    sanitized = sanitize_report(raw_report, sources=sources, evidence_items=evidence)

    assert UUID_PATTERN.search(sanitized.markdown) is None
    assert "[1]" in sanitized.markdown
    assert sanitized.citation_map[0].source_id == source_uuid


def test_sanitize_report_strips_unknown_bracketed_uuid():
    """Unrecognized UUIDs in brackets must be removed so internal identifiers are never shown."""
    unknown_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    sources = [
        Source(
            id="12345678-1234-1234-1234-123456789abc",
            title="Sample",
            url="https://example.com",
            content="Sample",
        )
    ]

    raw_markdown = f"This is an unverified claim [{unknown_uuid}]."
    raw_report = Report(
        markdown=raw_markdown,
        citation_map=[],
        total_citations=0,
        word_count=5,
        section_count=0,
    )

    sanitized = sanitize_report(raw_report, sources=sources)

    assert UUID_PATTERN.search(sanitized.markdown) is None
    assert unknown_uuid not in sanitized.markdown
    assert "This is an unverified claim." in sanitized.markdown


def test_claim_evidence_source_traceability_intact():
    """Verify that claim -> evidence -> source links remain unbroken across the full pipeline."""
    src1_id = "s1111111-1111-1111-1111-111111111111"
    src2_id = "s2222222-2222-2222-2222-222222222222"
    ev1_id = "e1111111-1111-1111-1111-111111111111"
    ev2_id = "e2222222-2222-2222-2222-222222222222"

    sources = [
        Source(id=src1_id, title="Source 1", url="https://s1.org", content="Content 1"),
        Source(id=src2_id, title="Source 2", url="https://s2.org", content="Content 2"),
    ]
    evidence = [
        Evidence(id=ev1_id, sub_question_id="sq1", source_id=src1_id, snippet="Snippet 1"),
        Evidence(id=ev2_id, sub_question_id="sq2", source_id=src2_id, snippet="Snippet 2"),
    ]
    claims = [
        Claim(id="c1", statement="Claim 1", evidence_ids=[ev1_id], verification_status="verified"),
        Claim(id="c2", statement="Claim 2", evidence_ids=[ev2_id], verification_status="verified"),
    ]

    # Verify claim 1 traces to source 1
    assert claims[0].evidence_ids[0] == ev1_id
    assert evidence[0].source_id == src1_id

    # Verify claim 2 traces to source 2
    assert claims[1].evidence_ids[0] == ev2_id
    assert evidence[1].source_id == src2_id

    report = Report(
        markdown="# Combined Findings\n\nClaim 1 statement [1]. Claim 2 statement [2].",
        citation_map=[],
        total_citations=0,
        word_count=10,
        section_count=1,
    )

    sanitized = sanitize_report(report, sources=sources, evidence_items=evidence)

    assert UUID_PATTERN.search(sanitized.markdown) is None
    markers = {entry.marker: entry.source_id for entry in sanitized.citation_map}
    assert markers["[1]"] == src1_id
    assert markers["[2]"] == src2_id
