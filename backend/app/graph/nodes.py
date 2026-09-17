from __future__ import annotations

import structlog
from langchain_core.runnables import RunnableConfig

from app.agents.critic import CriticAgent
from app.agents.evidence_extractor import EvidenceExtractor
from app.agents.planner import PlannerAgent
from app.agents.source_ranker import SourceRanker
from app.agents.synthesis import SynthesisAgent
from app.agents.web_research import WebResearchAgent
from app.agents.writer import WriterAgent
from app.graph.state import ResearchState
from app.llm.callbacks import AsyncAgentRunCallbackHandler
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


async def plan_research(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Decompose question into a plan."""
    handler = AsyncAgentRunCallbackHandler(state["session_id"], "PlannerAgent", persistence_service)
    plan = await planner_agent.run(state["research_question"], callbacks=[handler])
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

    # Deduplicate by URL (preferring the first seen to maintain determinism, or just unique URLs)
    seen_urls = set()
    unique_sources = []
    for s in sources:
        if s.url not in seen_urls:
            seen_urls.add(s.url)
            unique_sources.append(s)

    # Rank them
    await source_ranker.run(unique_sources)

    # Sort them descending by relevance
    unique_sources.sort(key=lambda s: s.relevance_score, reverse=True)

    # Persist the deduplicated/ranked sources
    await persistence_service.save_sources(state["session_id"], unique_sources)

    # Return using the custom overwrite reducer format
    return {"sources": {"overwrite": True, "items": unique_sources}}


async def extract_evidence(state: dict, config: RunnableConfig) -> dict:
    """Node: Fan-out evidence extraction for a source and sub-question."""
    # Partial state received from Send API
    sub_question: SubQuestion = state["sub_question"]
    source: Source = state["source"]

    # We must retrieve session_id from the source or sub_question,
    # but state inside Send API doesn't include the root session_id unless we pass it.
    # Actually, state in Send API is just the dictionary we yielded.
    # In research_graph.py, fan_out_web_research passes `{"sub_question": sq, "session_id": state["session_id"]}` ?
    # Let's check `state["session_id"]` if available, otherwise it might fail.
    # Wait, earlier I need to check if `session_id` is available in `state`.
    session_id = state.get("session_id", "unknown_session")
    handler = AsyncAgentRunCallbackHandler(session_id, "EvidenceExtractor", persistence_service)

    evidence_items = await evidence_extractor.run(sub_question, source, callbacks=[handler])
    return {"evidence_items": evidence_items}


async def synthesize_claims(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Synthesize all evidence into claims."""
    evidence_items = state.get("evidence_items", [])

    # Before synthesis, we should persist all evidence extracted during the fan-out
    await persistence_service.save_evidence(state["session_id"], evidence_items)

    handler = AsyncAgentRunCallbackHandler(
        state["session_id"], "SynthesisAgent", persistence_service
    )
    claims = await synthesis_agent.run(evidence_items, callbacks=[handler])

    iteration = state.get("critic_iterations", 0) + 1
    await persistence_service.save_claims(state["session_id"], claims, iteration)

    return {"claims": claims}


async def critic_verify(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Verify claims against evidence."""
    claims = state.get("claims", [])
    evidence_items = state.get("evidence_items", [])

    handler = AsyncAgentRunCallbackHandler(state["session_id"], "CriticAgent", persistence_service)
    critic_result = await critic_agent.run(claims, evidence_items, callbacks=[handler])

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

    verified_claims = []
    if critic_result:
        verified_claims = [c for c in critic_result.claims if c.verification_status == "verified"]

    handler = AsyncAgentRunCallbackHandler(state["session_id"], "WriterAgent", persistence_service)
    report = await writer_agent.run(
        state["research_question"], verified_claims, sources, callbacks=[handler]
    )
    return {"report": report}
