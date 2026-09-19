from __future__ import annotations

import asyncio
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
from app.graph.state import ResearchState
from app.llm.callbacks import AsyncAgentRunCallbackHandler
from app.llm.observability import get_langfuse_callback
from app.llm.router import LLMRouter
from app.schemas.agent import Source, SubQuestion
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
    import uuid

    # Deduplicate by URL (preferring the first seen to maintain determinism, or just unique URLs)
    seen_urls = set()
    unique_sources = []
    for s in sources:
        if s.url not in seen_urls:
            seen_urls.add(s.url)
            # Reassign deterministic ID to prevent foreign key violations on retries (Rule A-04)
            s.id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{s.url}"))
            unique_sources.append(s)

    # Rank them
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

    async with _get_extraction_semaphore():
        evidence_items = await evidence_extractor.run_batch(sub_question, sources, callbacks=callbacks)
        await asyncio.sleep(0.5)

    import uuid
    for ev in evidence_items:
        # Reassign deterministic ID to prevent foreign key violations on retries (Rule A-04)
        ev.id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{ev.source_id}:{ev.snippet[:50]}"))

    return {"evidence_items": evidence_items}


async def synthesize_claims(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Synthesize all evidence into claims."""
    evidence_items = state.get("evidence_items", [])

    # Before synthesis, we should persist all evidence extracted during the fan-out
    await persistence_service.save_evidence(state["session_id"], evidence_items)

    callbacks = _get_callbacks(state["session_id"], "SynthesisAgent")
    claims = await synthesis_agent.run(evidence_items, callbacks=callbacks)

    # Validate that all evidence_ids referenced by claims actually exist in evidence_items
    valid_evidence_ids = {str(e.id) for e in evidence_items}
    for claim in claims:
        # Filter out hallucinated IDs to prevent foreign key violations (Rule A-04)
        claim.evidence_ids = [eid for eid in claim.evidence_ids if str(eid) in valid_evidence_ids]

    iteration = state.get("critic_iterations", 0) + 1
    await persistence_service.save_claims(state["session_id"], claims, iteration)

    return {"claims": claims}


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

    callbacks = _get_callbacks(state["session_id"], "WriterAgent")
    report = await writer_agent.run(
        state["research_question"],
        verified_claims,
        sources,
        evidence_items=evidence_items,
        callbacks=callbacks,
    )
    return {"report": report}

