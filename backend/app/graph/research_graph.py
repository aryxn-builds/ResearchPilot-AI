from __future__ import annotations

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

# 1. Initialize the StateGraph
builder = StateGraph(ResearchState)

# 2. Add all nodes
builder.add_node("plan_research", plan_research)
builder.add_node("web_research", web_research)
builder.add_node("rank_sources", rank_sources)
builder.add_node("extract_evidence", extract_evidence)
builder.add_node("synthesize_claims", synthesize_claims)
builder.add_node("critic_verify", critic_verify)
builder.add_node("write_report", write_report)

# 3. Define the flow (Edges)
builder.add_edge(START, "plan_research")

# Fan-out to web_research
builder.add_conditional_edges(
    "plan_research", route_to_research, ["web_research", "rank_sources"]
)

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
