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
from app.llm.router import LLMRouter
from app.schemas.agent import Source, SubQuestion
from app.tools.tavily import TavilyTool

logger = structlog.get_logger(__name__)

# Initialize singletons for the graph nodes
llm_router = LLMRouter()
tavily_tool = TavilyTool()

planner_agent = PlannerAgent(llm_router)
web_research_agent = WebResearchAgent(tavily_tool)
source_ranker = SourceRanker()
evidence_extractor = EvidenceExtractor(llm_router)
synthesis_agent = SynthesisAgent(llm_router)
critic_agent = CriticAgent(llm_router)
writer_agent = WriterAgent(llm_router)


async def plan_research(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Decompose question into a plan."""
    plan = await planner_agent.run(state["research_question"])
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
    
    # We mutate the objects in-place rather than returning a new list
    # because the state uses operator.add and would duplicate them.
    await source_ranker.run(sources)
    return {}


async def extract_evidence(state: dict, config: RunnableConfig) -> dict:
    """Node: Fan-out evidence extraction for a source and sub-question."""
    # Partial state received from Send API
    sub_question: SubQuestion = state["sub_question"]
    source: Source = state["source"]
    
    evidence_items = await evidence_extractor.run(sub_question, source)
    return {"evidence_items": evidence_items}


async def synthesize_claims(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Synthesize all evidence into claims."""
    evidence_items = state.get("evidence_items", [])
    claims = await synthesis_agent.run(evidence_items)
    return {"claims": claims}


async def critic_verify(state: ResearchState, config: RunnableConfig) -> dict:
    """Node: Verify claims against evidence."""
    claims = state.get("claims", [])
    evidence_items = state.get("evidence_items", [])
    
    critic_result = await critic_agent.run(claims, evidence_items)
    
    current_iterations = state.get("critic_iterations", 0)
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
        
    report = await writer_agent.run(state["research_question"], verified_claims, sources)
    return {"report_markdown": report.markdown}
