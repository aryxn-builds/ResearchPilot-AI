from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.graph.edges import route_to_extraction, route_to_research, verify_claims_loop
from app.graph.nodes import (
    critic_verify,
    extract_evidence,
    plan_research,
    rank_sources,
    synthesize_claims,
    web_research,
    write_report,
)
from app.graph.state import ResearchState

logger = structlog.get_logger(__name__)


def timed_node(node: Callable[..., Awaitable[dict]]) -> Callable[..., Awaitable[dict]]:
    """Log each node's elapsed time, including waits and writes."""
    async def run(state: dict, config: RunnableConfig) -> dict:
        started = perf_counter()
        outcome = "failed"
        try:
            result = await node(state, config)
            outcome = "success"
            return result
        finally:
            logger.info("research_stage", session_id=state.get("session_id"),
                        stage=node.__name__, outcome=outcome,
                        duration_ms=round((perf_counter() - started) * 1000, 2))

    return run


# 1. Initialize the StateGraph
builder = StateGraph(ResearchState)

# 2. Add all nodes
builder.add_node("plan_research", timed_node(plan_research))
builder.add_node("web_research", timed_node(web_research))
builder.add_node("rank_sources", timed_node(rank_sources))
builder.add_node("extract_evidence", timed_node(extract_evidence))
builder.add_node("synthesize_claims", timed_node(synthesize_claims))
builder.add_node("critic_verify", timed_node(critic_verify))
builder.add_node("write_report", timed_node(write_report))

# 3. Define the flow (Edges)
builder.add_edge(START, "plan_research")

# Fan-out to web_research
builder.add_conditional_edges("plan_research", route_to_research, ["web_research", "rank_sources"])

# After all web_research parallel tasks complete, proceed to ranking
builder.add_edge("web_research", "rank_sources")

# Fan-out to extract_evidence
builder.add_conditional_edges(
    "rank_sources", route_to_extraction, ["extract_evidence", "synthesize_claims"]
)

# After all extraction tasks complete, proceed to synthesis
builder.add_edge("extract_evidence", "synthesize_claims")

# Critic validation loop
builder.add_edge("synthesize_claims", "critic_verify")
builder.add_conditional_edges(
    "critic_verify",
    verify_claims_loop,
    {"synthesize_claims": "synthesize_claims", "write_report": "write_report"},
)

# Finish
builder.add_edge("write_report", END)

# 4. Compile the graph
research_graph = builder.compile()
