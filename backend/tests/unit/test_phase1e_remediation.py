"""
Tests for Phase 1E remediation fixes:
A — Task-aware source routing (route_to_extraction)
B — Duplicate URL handling with preserved task provenance
C — Concurrency semaphore respected
D — Provider fallback (Gemini → Groq → OpenRouter)
E — ValidationError does not cascade to next provider
F — Regression (all existing graph tests still pass)
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import ProviderExhaustedError
from app.graph.edges import route_to_extraction
from app.graph.state import ResearchState
from app.llm.router import LLMRouter
from app.schemas.agent import (
    Claim,
    CriticResult,
    Evidence,
    Report,
    ResearchPlan,
    Source,
    SubQuestion,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def make_sub_question(question: str = "Q?") -> SubQuestion:
    return SubQuestion(id=str(uuid.uuid4()), question=question, research_type="web")


def make_source(task_id: uuid.UUID, url: str = "https://example.com") -> Source:
    return Source(
        id=str(uuid.uuid4()),
        task_id=task_id,
        url=url,
        title="Test",
        content="Test content for evidence extraction.",
        relevance_score=0.9,
    )


def make_state(plan: ResearchPlan, sources: list[Source]) -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "research_question": "Test?",
        "research_plan": plan,
        "sources": sources,
        "evidence_items": [],
        "claims": [],
        "critic_result": None,
        "critic_iterations": 0,
        "report": None,
    }


# ─────────────────────────────────────────────────────────────
# TEST A: Task-aware routing
# ─────────────────────────────────────────────────────────────

class TestTaskAwareRouting:
    """Task A: Each sub-question receives ONLY its own sources."""

    def test_task_a_only_receives_task_a_sources(self):
        """Sources owned by task A must not appear in task B or C sends."""
        sq_a = make_sub_question("What is Python 3.11?")
        sq_b = make_sub_question("What is Python 3.12?")
        sq_c = make_sub_question("What are performance changes?")

        src_a1 = make_source(sq_a.id, "https://a1.com")
        src_a2 = make_source(sq_a.id, "https://a2.com")
        src_b1 = make_source(sq_b.id, "https://b1.com")
        src_b2 = make_source(sq_b.id, "https://b2.com")
        src_c1 = make_source(sq_c.id, "https://c1.com")

        plan = ResearchPlan(sub_questions=[sq_a, sq_b, sq_c])
        state = make_state(plan, [src_a1, src_a2, src_b1, src_b2, src_c1])

        sends = route_to_extraction(state)

        # Collect which sources each task actually gets
        task_to_sources: dict[str, set[str]] = {}
        for send in sends:
            sq_id = str(send.arg["sub_question"].id)
            url = send.arg["source"].url
            task_to_sources.setdefault(sq_id, set()).add(url)

        # Task A should only get A sources
        assert task_to_sources.get(str(sq_a.id), set()) == {"https://a1.com", "https://a2.com"}
        # Task B should only get B sources
        assert task_to_sources.get(str(sq_b.id), set()) == {"https://b1.com", "https://b2.com"}
        # Task C should only get C sources
        assert task_to_sources.get(str(sq_c.id), set()) == {"https://c1.com"}

        # Cross-contamination must NOT exist
        a_sources = task_to_sources.get(str(sq_a.id), set())
        assert "https://b1.com" not in a_sources
        assert "https://c1.com" not in a_sources

        b_sources = task_to_sources.get(str(sq_b.id), set())
        assert "https://a1.com" not in b_sources
        assert "https://c1.com" not in b_sources

    def test_task_source_cap_respected(self):
        """Per-task source cap (RESEARCH_MAX_SOURCES_PER_TASK) must be respected."""
        sq = make_sub_question("Q?")
        # Create 10 sources for the same task — far above the default cap of 5
        sources = [make_source(sq.id, f"https://site{i}.com") for i in range(10)]

        plan = ResearchPlan(sub_questions=[sq])
        state = make_state(plan, sources)

        sends = route_to_extraction(state)

        # Should be capped at RESEARCH_MAX_SOURCES_PER_TASK (default 5)
        from app.core.config import settings
        assert len(sends) <= settings.RESEARCH_MAX_SOURCES_PER_TASK

    def test_task_without_sources_generates_no_sends(self):
        """A sub-question with no sources should not generate any extraction sends."""
        sq_a = make_sub_question("A?")
        sq_b = make_sub_question("B?")
        src_a = make_source(sq_a.id, "https://a.com")
        # sq_b gets no sources

        plan = ResearchPlan(sub_questions=[sq_a, sq_b])
        state = make_state(plan, [src_a])

        sends = route_to_extraction(state)

        sq_ids_with_sends = {str(s.arg["sub_question"].id) for s in sends}
        assert str(sq_a.id) in sq_ids_with_sends
        assert str(sq_b.id) not in sq_ids_with_sends

    def test_no_sources_returns_synthesize_claims(self):
        """With no sources at all, edge must skip to synthesize_claims."""
        sq = make_sub_question("Q?")
        plan = ResearchPlan(sub_questions=[sq])
        state = make_state(plan, [])  # no sources

        result = route_to_extraction(state)
        assert result == "synthesize_claims"

    def test_flagged_sources_excluded(self):
        """Flagged sources must not be included in extraction sends."""
        sq = make_sub_question("Q?")
        good_src = make_source(sq.id, "https://good.com")
        bad_src = make_source(sq.id, "https://bad.com")
        bad_src.is_flagged = True

        plan = ResearchPlan(sub_questions=[sq])
        state = make_state(plan, [good_src, bad_src])

        sends = route_to_extraction(state)
        urls = {s.arg["source"].url for s in sends}

        assert "https://good.com" in urls
        assert "https://bad.com" not in urls


# ─────────────────────────────────────────────────────────────
# TEST B: Duplicate URL — task provenance preserved
# ─────────────────────────────────────────────────────────────

class TestDuplicateUrlHandling:
    """Test B: When the same URL is discovered by two tasks, the first task's
    source must survive after deduplication, preserving its task_id provenance.
    The DB UNIQUE(session_id, url) constraint is satisfied by upsert on_conflict.
    """

    @pytest.mark.asyncio
    async def test_dedup_preserves_first_seen_task_id(self):
        """rank_sources keeps only the first-seen source per URL (deterministic)."""
        from app.graph.nodes import rank_sources

        sq_a = make_sub_question("A?")
        sq_b = make_sub_question("B?")

        # Same URL discovered by both tasks
        src_a = make_source(sq_a.id, "https://shared.com")
        src_b = make_source(sq_b.id, "https://shared.com")

        with patch("app.graph.nodes.persistence_service") as mock_ps:
            mock_ps.save_sources = AsyncMock()

            state = {
                "session_id": "test-session",
                "research_question": "Q?",
                "research_plan": ResearchPlan(sub_questions=[sq_a, sq_b]),
                "sources": [src_a, src_b],  # Both have same URL
                "evidence_items": [],
                "claims": [],
                "critic_result": None,
                "critic_iterations": 0,
                "report": None,
            }

            result = await rank_sources(state, config=None)

        # After dedup, only one source with https://shared.com remains
        final_sources = result["sources"]["items"]
        shared_sources = [s for s in final_sources if s.url == "https://shared.com"]
        assert len(shared_sources) == 1

        # The surviving source must retain its original task_id (first seen = sq_a)
        assert shared_sources[0].task_id == sq_a.id


# ─────────────────────────────────────────────────────────────
# TEST C: Concurrency semaphore
# ─────────────────────────────────────────────────────────────

class TestConcurrencyLimit:
    """Test C: The extraction semaphore bounds concurrent LLM calls."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """No more than EVIDENCE_EXTRACTION_CONCURRENCY extractions run simultaneously."""
        from app.core.config import settings

        concurrency_limit = settings.EVIDENCE_EXTRACTION_CONCURRENCY
        max_observed = 0
        active = 0

        async def fake_extraction(*args, **kwargs):
            nonlocal active, max_observed
            active += 1
            max_observed = max(max_observed, active)
            await asyncio.sleep(0.01)  # Simulate I/O
            active -= 1
            return []

        sq = make_sub_question("Q?")
        sources = [make_source(sq.id, f"https://site{i}.com") for i in range(20)]

        # Reset the module-level semaphore so our test uses the configured limit
        import app.graph.nodes as nodes_module
        nodes_module._evidence_extraction_semaphore = None

        with (
            patch("app.graph.nodes.evidence_extractor") as mock_extractor,
            patch("app.graph.nodes.persistence_service") as mock_ps,
        ):
            mock_extractor.run = fake_extraction
            mock_ps.save_agent_run = AsyncMock()

            tasks = []
            for source in sources:
                state = {
                    "sub_question": sq,
                    "source": source,
                    "session_id": "test",
                }
                tasks.append(
                    asyncio.create_task(
                        nodes_module.extract_evidence(state, config=None)
                    )
                )

            await asyncio.gather(*tasks)

        assert max_observed <= concurrency_limit, (
            f"Observed {max_observed} concurrent extractions, limit is {concurrency_limit}"
        )


# ─────────────────────────────────────────────────────────────
# TEST D: Provider fallback chain
# ─────────────────────────────────────────────────────────────

class TestProviderFallback:
    """Test D: Gemini success, Gemini→Groq fallback, Gemini+Groq→OpenRouter fallback."""

    def _make_router(self) -> LLMRouter:
        """Create a bare LLMRouter instance without initialising real providers."""
        router = LLMRouter.__new__(LLMRouter)
        router._gemini_permanent_fail = False
        router._groq_permanent_fail = False
        router._openrouter_permanent_fail = False
        return router

    def _chain_mock(self, return_value=None, side_effect=None) -> MagicMock:
        """Build a MagicMock that simulates model.with_structured_output() → chain.
        chain.ainvoke() is an AsyncMock that returns the given value or raises.
        """
        chain = MagicMock()
        if side_effect is not None:
            chain.ainvoke = AsyncMock(side_effect=side_effect)
        else:
            chain.ainvoke = AsyncMock(return_value=return_value)

        provider = MagicMock()
        provider.with_structured_output.return_value = chain
        return provider

    @pytest.mark.asyncio
    async def test_gemini_success_no_fallback(self):
        """When Gemini succeeds, Groq and OpenRouter are never called."""
        from pydantic import BaseModel

        class SimpleOutput(BaseModel):
            value: str

        expected = SimpleOutput(value="test")
        router = self._make_router()

        router.gemini = self._chain_mock(return_value=expected)
        router.groq = self._chain_mock(return_value=expected)
        router.openrouter = self._chain_mock(return_value=expected)

        result = await router.generate_structured("prompt", SimpleOutput)

        assert result == expected
        router.groq.with_structured_output.assert_not_called()
        router.openrouter.with_structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_gemini_fail_falls_back_to_groq(self):
        """Transient Gemini failure falls back to Groq."""
        from pydantic import BaseModel

        class SimpleOutput(BaseModel):
            value: str

        expected = SimpleOutput(value="groq_result")
        router = self._make_router()

        router.gemini = self._chain_mock(side_effect=RuntimeError("Gemini transient error"))
        router.groq = self._chain_mock(return_value=expected)
        router.openrouter = None

        result = await router.generate_structured("prompt", SimpleOutput)
        assert result == expected

    @pytest.mark.asyncio
    async def test_gemini_groq_fail_falls_back_to_openrouter(self):
        """Transient Gemini and Groq failures both fall back to OpenRouter."""
        from pydantic import BaseModel

        class SimpleOutput(BaseModel):
            value: str

        expected = SimpleOutput(value="openrouter_result")
        router = self._make_router()

        router.gemini = self._chain_mock(side_effect=RuntimeError("Gemini down"))
        router.groq = self._chain_mock(side_effect=RuntimeError("Groq down"))
        router.openrouter = self._chain_mock(return_value=expected)

        result = await router.generate_structured("prompt", SimpleOutput)
        assert result == expected

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises_provider_exhausted(self):
        """When all providers fail, ProviderExhaustedError is raised."""
        from pydantic import BaseModel

        class SimpleOutput(BaseModel):
            value: str

        router = self._make_router()
        err = RuntimeError("Provider down")

        router.gemini = self._chain_mock(side_effect=err)
        router.groq = self._chain_mock(side_effect=err)
        router.openrouter = self._chain_mock(side_effect=err)

        with pytest.raises(ProviderExhaustedError):
            await router.generate_structured("prompt", SimpleOutput)


# ─────────────────────────────────────────────────────────────
# TEST E: ValidationError does NOT cascade
# ─────────────────────────────────────────────────────────────

class TestValidationErrorNoCascade:
    """Test E: A Pydantic ValidationError from Gemini must be re-raised immediately,
    not silently swallowed and cascaded to Groq or OpenRouter.
    Schema errors are prompt-level bugs, not provider failures.
    """

    @pytest.mark.asyncio
    async def test_gemini_validation_error_raises_immediately(self):
        """ValidationError from Gemini is re-raised without calling Groq."""
        from pydantic import BaseModel, ValidationError as PydanticValidationError

        class SimpleOutput(BaseModel):
            value: str

        router = LLMRouter.__new__(LLMRouter)
        router._gemini_permanent_fail = False
        router._groq_permanent_fail = False
        router._openrouter_permanent_fail = False

        # Build a real ValidationError by constructing it via Pydantic
        try:
            SimpleOutput.model_validate({"value": None, "unexpected_field": 999})
        except PydanticValidationError as ve:
            real_validation_error = ve

        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=real_validation_error)
        mock_gemini = MagicMock()
        mock_gemini.with_structured_output.return_value = chain

        mock_groq = MagicMock()
        router.gemini = mock_gemini
        router.groq = mock_groq
        router.openrouter = None

        with pytest.raises(PydanticValidationError):
            await router.generate_structured("prompt", SimpleOutput)

        # Groq must NOT have been consulted
        mock_groq.with_structured_output.assert_not_called()


# ─────────────────────────────────────────────────────────────
# TEST D-EXTRA: Permanent-error fast-fail
# ─────────────────────────────────────────────────────────────

class TestPermanentErrorFastFail:
    """Test that 404 model-not-found errors mark provider as permanently failed."""

    @pytest.mark.asyncio
    async def test_404_marks_gemini_permanently_failed(self):
        """A 404 error on first Gemini call must mark it permanently failed
        so subsequent calls skip it without another roundtrip."""
        from pydantic import BaseModel

        class SimpleOutput(BaseModel):
            value: str

        router = LLMRouter.__new__(LLMRouter)
        router._gemini_permanent_fail = False
        router._groq_permanent_fail = False
        router._openrouter_permanent_fail = False

        err_404 = Exception("404 model not found: gemini-1.5-flash does not exist")
        expected = SimpleOutput(value="ok")

        gemini_chain = MagicMock()
        gemini_chain.ainvoke = AsyncMock(side_effect=err_404)
        mock_gemini = MagicMock()
        mock_gemini.with_structured_output.return_value = gemini_chain

        groq_chain = MagicMock()
        groq_chain.ainvoke = AsyncMock(return_value=expected)
        mock_groq = MagicMock()
        mock_groq.with_structured_output.return_value = groq_chain


        router.gemini = mock_gemini
        router.groq = mock_groq
        router.openrouter = None


        # First call: Gemini gets 404, Groq succeeds
        result = await router.generate_structured("prompt", SimpleOutput)
        assert result == expected
        assert router._gemini_permanent_fail is True

        # Second call: Gemini should be skipped entirely
        mock_gemini_chain2 = AsyncMock(return_value=expected)
        mock_gemini2 = MagicMock()
        mock_gemini2.with_structured_output.return_value = mock_gemini_chain2
        router.gemini = mock_gemini2  # Replace to detect if called

        result2 = await router.generate_structured("prompt", SimpleOutput)
        assert result2 == expected
        # Gemini was NOT invoked on the second call
        mock_gemini2.with_structured_output.assert_not_called()
