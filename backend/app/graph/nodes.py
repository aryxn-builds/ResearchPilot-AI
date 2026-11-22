from __future__ import annotations

import asyncio
import re
import uuid
from time import perf_counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog
from langchain_core.runnables import RunnableConfig

from app.agents.critic import CriticAgent
from app.agents.evidence_extractor import EvidenceExtractor
from app.agents.planner import PlannerAgent
from app.agents.source_ranker import SourceRanker
from app.agents.synthesis import SynthesisAgent
from app.agents.web_research import WebResearchAgent
from app.agents.writer import WriterAgent
from app.core.config import settings
from app.core.research_mode import fast_research
from app.graph.state import ResearchState
from app.llm.callbacks import AsyncAgentRunCallbackHandler
from app.llm.observability import get_langfuse_callback
from app.llm.router import LLMRouter
from app.schemas.agent import ResearchPlan, Source, SubQuestion
from app.services.persistence import PersistenceService
from app.tools.tavily import TavilyTool

logger = structlog.get_logger(__name__)

# Initialize singletons for the graph nodes
llm_router = LLMRouter()
tavily_tool = TavilyTool()
persistence_service = PersistenceService()

planner_agent = PlannerAgent(llm_router)
web_research_agent = WebResearchAgent(tavily_tool)
source_ranker = SourceRanker()
evidence_extractor = EvidenceExtractor(llm_router)
synthesis_agent = SynthesisAgent(llm_router)
critic_agent = CriticAgent(llm_router)
writer_agent = WriterAgent(llm_router)


def _get_callbacks(session_id: str, agent_name: str) -> list:
    """Return persistence callback handler plus optional Langfuse handler if healthy."""
    handlers = [AsyncAgentRunCallbackHandler(session_id, agent_name, persistence_service)]
    handlers.extend(get_langfuse_callback(session_id))
    return handlers


# Bounded concurrency semaphore for evidence extraction.
# Prevents fan-out from hammering the LLM provider with too many simultaneous requests,
# which caused 402 Payment Required errors during the Phase 1D E2E verification.
# Limit is configurable via EVIDENCE_EXTRACTION_CONCURRENCY in settings.
_evidence_extraction_semaphore: asyncio.Semaphore | None = None


def _get_extraction_semaphore() -> asyncio.Semaphore:
    """Return the module-level extraction semaphore, creating it lazily.

    Lazy creation ensures it is bound to the correct event loop at runtime.
    """
    global _evidence_extraction_semaphore
    if _evidence_extraction_semaphore is None:
        _evidence_extraction_semaphore = asyncio.Semaphore(
            settings.EVIDENCE_EXTRACTION_CONCURRENCY
        )
    return _evidence_extraction_semaphore


async def plan_research(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Decompose question into a plan."""
    if fast_research.get():
        plan = ResearchPlan(sub_questions=[SubQuestion(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{state['session_id']}:fast-plan")),
            question=state["research_question"],
            research_type="web",
        )])
    else:
        callbacks = _get_callbacks(state["session_id"], "PlannerAgent")
        plan = await planner_agent.run(state["research_question"], callbacks=callbacks)
    await persistence_service.save_plan(state["session_id"], plan)
    return {"research_plan": plan, "critic_iterations": 0}


async def web_research(state: dict, config: RunnableConfig) -> dict:
    """Node: Fan-out research for a single sub-question."""
    # Partial state received from Send API
    sub_question: SubQuestion = state["sub_question"]
    sources = await web_research_agent.run(sub_question)
    return {"sources": sources}


async def rank_sources(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Score and rank all gathered sources."""
    sources = state.get("sources", [])
    session_id = state.get("session_id")

    if fast_research.get():
        await source_ranker.run(sources)
        terms = set(re.findall(r"[a-z0-9]{3,}", state["research_question"].lower()))
        for source in sources:
            words = set(re.findall(r"[a-z0-9]{3,}", (source.title + " " + source.content).lower()))
            source.relevance_score = len(terms & words) / max(1, len(terms))
        sources = sorted(sources, key=lambda s: (s.relevance_score, s.credibility_score), reverse=True)

    # Deduplicate by URL (preferring the first seen to maintain determinism, or just unique URLs)
    seen_urls = set()
    unique_sources = []
    fingerprints: list[set[tuple[str, ...]]] = []
    for s in sources:
        key = s.url
        if fast_research.get():
            try:
                parsed = urlsplit(s.url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
                    continue
            except ValueError:
                continue
            query = sorted((k, v) for k, v in parse_qsl(parsed.query)
                           if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"})
            key = urlunsplit(("", parsed.netloc.lower(), parsed.path.rstrip("/"), urlencode(query), ""))
            words = re.findall(r"\w+", s.content.lower())
            shingles = set(zip(words, words[1:], words[2:]))
            if (key in seen_urls or not shingles or any(
                len(shingles & previous) / len(shingles | previous) >= 0.85
                for previous in fingerprints
            )):
                continue
            fingerprints.append(shingles)
        if key not in seen_urls:
            seen_urls.add(key)
            # Reassign deterministic ID to prevent foreign key violations on retries (Rule A-04)
            s.id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{s.url}"))
            unique_sources.append(s)
            if fast_research.get() and len(unique_sources) >= settings.FAST_MAX_SOURCES:
                break

    # Rank them
    if not fast_research.get():
        await source_ranker.run(unique_sources)

    # Sort them descending by relevance
    unique_sources.sort(key=lambda s: s.relevance_score, reverse=True)

    # Persist the deduplicated/ranked sources
    await persistence_service.save_sources(session_id, unique_sources)

    # Return using the custom overwrite reducer format
    return {"sources": {"overwrite": True, "items": unique_sources}}


async def extract_evidence(state: dict, config: RunnableConfig) -> dict:
    """Node: Fan-out evidence extraction for sources and sub-question.

    Bounded by _get_extraction_semaphore() to prevent provider rate-limit errors
    caused by too many simultaneous LLM calls during parallel fan-out.
    """
    # Partial state received from Send API
    sub_question: SubQuestion = state["sub_question"]
    sources: list[Source] = state.get("sources") or ([state["source"]] if "source" in state else [])
    session_id = state.get("session_id", "unknown_session")
    callbacks = _get_callbacks(session_id, "EvidenceExtractor")

    queued_at = perf_counter()
    async with _get_extraction_semaphore():
        logger.info("research_evidence_queue", session_id=session_id,
                    wait_ms=round((perf_counter() - queued_at) * 1000, 2))
        evidence_items = await evidence_extractor.run_batch(sub_question, sources, callbacks=callbacks)
        if not fast_research.get():
            await asyncio.sleep(0.5)

    for ev in evidence_items:
        # Reassign deterministic ID to prevent foreign key violations on retries (Rule A-04)
        ev.id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{ev.source_id}:{ev.snippet}"))

    return {"evidence_items": evidence_items}


async def synthesize_claims(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Synthesize all evidence into claims."""
    evidence_items = state.get("evidence_items", [])

    if fast_research.get():
        evidence_items = list({item.id: item for item in evidence_items}.values())
        evidence_items = evidence_items[:settings.FAST_MAX_EVIDENCE]
        if not evidence_items:
            raise ValueError("Fast Research found no attributable evidence.")

    # Before synthesis, we should persist all evidence extracted during the fan-out
    if not state.get("critic_iterations"):
        await persistence_service.save_evidence(state["session_id"], evidence_items)

    callbacks = _get_callbacks(state["session_id"], "SynthesisAgent")
    claims = await synthesis_agent.run(evidence_items, callbacks=callbacks)

    # Validate that all evidence_ids referenced by claims actually exist in evidence_items
    valid_evidence_ids = {str(e.id) for e in evidence_items}
    for claim in claims:
        # Filter out hallucinated IDs to prevent foreign key violations (Rule A-04)
        claim.evidence_ids = [eid for eid in claim.evidence_ids if str(eid) in valid_evidence_ids]

    if fast_research.get():
        claims = [claim for claim in claims if claim.evidence_ids][:6]
        for claim in claims:
            claim.verification_status = "pending"

    iteration = state.get("critic_iterations", 0) + 1
    await persistence_service.save_claims(state["session_id"], claims, iteration)

    update = {"claims": claims}
    if fast_research.get():
        update["evidence_items"] = {"overwrite": True, "items": evidence_items}
    return update


async def critic_verify(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Verify claims against evidence."""
    claims = state.get("claims", [])
    evidence_items = state.get("evidence_items", [])

    callbacks = _get_callbacks(state["session_id"], "CriticAgent")
    critic_result = await critic_agent.run(claims, evidence_items, callbacks=callbacks)

    current_iterations = state.get("critic_iterations", 0)
    await persistence_service.save_critic_result(
        state["session_id"], critic_result, current_iterations + 1
    )

    return {
        "critic_result": critic_result,
        "critic_iterations": current_iterations + 1,
    }


async def write_report(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Generate the final markdown report."""
    critic_result = state.get("critic_result")
    sources = state.get("sources", [])
    evidence_items = state.get("evidence_items", [])

    verified_claims = []
    if critic_result:
        verified_claims = [c for c in critic_result.claims if c.verification_status == "verified"]

    if fast_research.get():
        checked = critic_result.claims if critic_result else []
        return {"report": writer_agent.render_verified(checked, sources, evidence_items)}

    callbacks = _get_callbacks(state["session_id"], "WriterAgent")
    report = await writer_agent.run(
        state["research_question"],
        verified_claims,
        sources,
        evidence_items=evidence_items,
        callbacks=callbacks,
    )
    return {"report": report}

