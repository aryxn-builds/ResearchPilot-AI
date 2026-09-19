"""Phase 1I Reliability & Hardening Tests.

Validates:
1. Provider preflight / health check mechanism.
2. Failure classification (permanent fast-fail vs transient retry).
3. Fallback routing chain (Gemini -> Groq -> OpenRouter).
4. EvidenceExtractor batching with source attribution preservation.
5. Evidence traceability (programmatic UUID5 domain IDs).
6. Supabase transient failure retry mechanism.
7. Langfuse safe degradation (non-blocking when unavailable/unauthorized).
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from app.agents.evidence_extractor import EvidenceExtractor
from app.core.config import settings
from app.core.database import execute_with_retry
from app.core.exceptions import ProviderExhaustedError
from app.graph.edges import route_to_extraction
from app.llm.observability import check_langfuse_health, get_langfuse_callback
from app.llm.router import LLMRouter
from app.schemas.agent import Evidence, ResearchPlan, Source, SubQuestion


class MockSchema(BaseModel):
    status: str
    summary: str


# ─────────────────────────────────────────────────────────────
# 1. PROVIDER PREFLIGHT & HEALTH
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_provider_preflight_missing_key():
    """Validates that a provider with a missing key reports unhealthy immediately."""
    router = LLMRouter.__new__(LLMRouter)
    router._gemini_permanent_fail = False
    router._groq_permanent_fail = False
    router._openrouter_permanent_fail = False

    with patch.object(settings, "GEMINI_API_KEY", ""):
        res = await router.validate_provider_health("gemini")
        assert res["healthy"] is False
        assert "not configured" in res["error"]


@pytest.mark.asyncio
async def test_provider_preflight_success():
    """Validates that a provider passing structured output reports healthy."""
    router = LLMRouter.__new__(LLMRouter)
    mock_gemini = MagicMock()
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=MockSchema(status="healthy", summary="ok"))
    mock_gemini.with_structured_output.return_value = chain
    router.gemini = mock_gemini

    with patch.object(settings, "GEMINI_API_KEY", "valid-key"):
        res = await router.validate_provider_health("gemini")
        assert res["healthy"] is True
        assert res["provider"] == "gemini"


# ─────────────────────────────────────────────────────────────
# 2. FAILURE CLASSIFICATION & PERMANENT FAST-FAIL
# ─────────────────────────────────────────────────────────────


def test_failure_classification_permanent_vs_transient():
    """Distinguishes permanent deterministic errors from transient retryable errors."""
    router = LLMRouter.__new__(LLMRouter)

    # Permanent: decommissioned model, 404 not found, 401 unauthorized, 402 payment, daily quota
    assert router._is_permanent_error(Exception("404 NotFound: model does not exist")) is True
    assert router._is_permanent_error(Exception("Model llama-3.1-70b-versatile has been decommissioned")) is True
    assert router._is_permanent_error(Exception("401 Unauthorized: Invalid API Key")) is True
    assert router._is_permanent_error(Exception("402 Payment Required: Insufficient balance")) is True
    assert router._is_permanent_error(Exception("Quota exceeded for metric: generaterequestsperday, limit: 500")) is True

    # Transient: 429 rate limit, 500 server error, timeout
    assert router._is_permanent_error(Exception("429 Too Many Requests")) is False
    assert router._is_permanent_error(Exception("503 Service Unavailable")) is False
    assert router._is_permanent_error(Exception("ConnectTimeout: connection timed out")) is False


@pytest.mark.asyncio
async def test_permanent_error_fast_fails_to_next_provider():
    """Permanent errors do NOT retry 3 times; they fail fast to the next provider."""
    router = LLMRouter.__new__(LLMRouter)
    router._gemini_permanent_fail = False
    router._groq_permanent_fail = False
    router._openrouter_permanent_fail = False

    expected = MockSchema(status="healthy", summary="from groq")

    gemini_chain = MagicMock()
    gemini_chain.ainvoke = AsyncMock(side_effect=Exception("model_decommissioned"))
    mock_gemini = MagicMock()
    mock_gemini.with_structured_output.return_value = gemini_chain

    groq_chain = MagicMock()
    groq_chain.ainvoke = AsyncMock(return_value=expected)
    mock_groq = MagicMock()
    mock_groq.with_structured_output.return_value = groq_chain

    router.gemini = mock_gemini
    router.groq = mock_groq
    router.openrouter = None

    result = await router.generate_structured("prompt", MockSchema)
    assert result == expected
    # Gemini should only have been called ONCE before fast-failing
    assert gemini_chain.ainvoke.call_count == 1
    assert router._gemini_permanent_fail is True


# ─────────────────────────────────────────────────────────────
# 3. FALLBACK CHAIN (Gemini -> Groq -> OpenRouter)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_chain_all_three_providers():
    """Full fallback chain from Gemini to Groq to OpenRouter."""
    router = LLMRouter.__new__(LLMRouter)
    router._gemini_permanent_fail = False
    router._groq_permanent_fail = False
    router._openrouter_permanent_fail = False

    expected = MockSchema(status="healthy", summary="from openrouter")

    g_chain = MagicMock()
    g_chain.ainvoke = AsyncMock(side_effect=Exception("gemini 429 rate limit"))
    mock_gemini = MagicMock()
    mock_gemini.with_structured_output.return_value = g_chain

    gr_chain = MagicMock()
    gr_chain.ainvoke = AsyncMock(side_effect=Exception("groq 500 error"))
    mock_groq = MagicMock()
    mock_groq.with_structured_output.return_value = gr_chain

    or_chain = MagicMock()
    or_chain.ainvoke = AsyncMock(return_value=expected)
    mock_openrouter = MagicMock()
    mock_openrouter.with_structured_output.return_value = or_chain

    router.gemini = mock_gemini
    router.groq = mock_groq
    router.openrouter = mock_openrouter

    result = await router.generate_structured("prompt", MockSchema)
    assert result == expected
    assert or_chain.ainvoke.call_count == 1


# ─────────────────────────────────────────────────────────────
# 4. EVIDENCE EXTRACTION BATCHING & SOURCE TRACEABILITY
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_evidence_extraction_batching_and_attribution():
    """Batch of sources processes in 1 LLM call while preserving source IDs."""
    sub_q = SubQuestion(id=str(uuid.uuid4()), question="What are recent quantum developments?", research_type="web")
    src1 = Source(
        id=str(uuid.uuid4()),
        url="https://quantum1.org",
        title="Q1",
        content="Google announced Willow quantum chip with exponential error reduction.",
    )
    src2 = Source(
        id=str(uuid.uuid4()),
        url="https://quantum2.org",
        title="Q2",
        content="Neutral atom qubits demonstrated high 2-qubit gate fidelities.",
    )

    class RawSnippet(BaseModel):
        snippet: str
        source_id: str

    class FakeExtractionResult(BaseModel):
        evidence_items: list[RawSnippet]

    fake_result = FakeExtractionResult(
        evidence_items=[
            RawSnippet(snippet="Willow quantum chip with exponential error reduction.", source_id=str(src1.id)),
            RawSnippet(snippet="Neutral atom qubits demonstrated high 2-qubit gate fidelities.", source_id=str(src2.id)),
        ]
    )

    mock_router = AsyncMock()
    mock_router.generate_structured = AsyncMock(return_value=fake_result)

    extractor = EvidenceExtractor(mock_router)
    evidence = await extractor.run_batch(sub_q, [src1, src2])

    assert len(evidence) == 2
    # Only 1 LLM call for both sources!
    assert mock_router.generate_structured.call_count == 1

    # Exact source mapping preserved
    assert evidence[0].source_id == src1.id
    assert evidence[1].source_id == src2.id
    # Sub-question association preserved
    assert evidence[0].sub_question_id == sub_q.id
    assert evidence[1].sub_question_id == sub_q.id


def test_route_to_extraction_batch_size_chunking():
    """Edges chunk task sources according to EVIDENCE_BATCH_SIZE."""
    sq = SubQuestion(id=str(uuid.uuid4()), question="SubQ?", research_type="web")
    sources = [
        Source(id=str(uuid.uuid4()), task_id=sq.id, url=f"https://site{i}.com", title=f"S{i}", content=f"Content {i}")
        for i in range(4)
    ]
    plan = ResearchPlan(sub_questions=[sq])
    state = {
        "session_id": "test-session",
        "research_plan": plan,
        "sources": sources,
    }

    with patch.object(settings, "EVIDENCE_BATCH_SIZE", 2), patch.object(settings, "RESEARCH_MAX_SOURCES_PER_TASK", 5):
        sends = route_to_extraction(state)
        # 4 sources with batch size 2 = 2 Sends
        assert len(sends) == 2
        assert len(sends[0].arg["sources"]) == 2
        assert len(sends[1].arg["sources"]) == 2


# ─────────────────────────────────────────────────────────────
# 5. SUPABASE TRANSIENT RETRY
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_supabase_transient_retry_success():
    """execute_with_retry recovers from transient network errors."""
    import httpx

    calls = 0

    async def transient_op():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectTimeout("Connection timed out")
        return {"data": [{"id": 1}]}

    result = await execute_with_retry(transient_op, max_retries=3, base_delay=0.001)
    assert result == {"data": [{"id": 1}]}
    assert calls == 3


@pytest.mark.asyncio
async def test_supabase_permanent_error_no_blind_retry():
    """Non-network errors (e.g. ValueError) fail fast without retrying."""
    calls = 0

    async def broken_op():
        nonlocal calls
        calls += 1
        raise ValueError("Invalid schema query")

    with pytest.raises(ValueError, match="Invalid schema query"):
        await execute_with_retry(broken_op, max_retries=3, base_delay=0.001)

    assert calls == 1


# ─────────────────────────────────────────────────────────────
# 6. LANGFUSE SAFE OBSERVABILITY
# ─────────────────────────────────────────────────────────────


def test_langfuse_safe_degradation_when_unauthorized():
    """When Langfuse credentials are unauthorized, get_langfuse_callback returns [] without crashing."""
    with patch("app.llm.observability.check_langfuse_health", return_value={"status": "unauthorized"}):
        callbacks = get_langfuse_callback("session-123")
        assert callbacks == []


def test_langfuse_safe_degradation_when_disabled():
    """When Langfuse is disabled, returns empty callback list."""
    with patch.object(settings, "LANGFUSE_ENABLED", False):
        health = check_langfuse_health(force_refresh=True)
        assert health["status"] == "disabled"
        assert get_langfuse_callback("session-123") == []
