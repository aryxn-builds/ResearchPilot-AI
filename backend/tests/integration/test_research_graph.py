import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.graph.research_graph import research_graph
from app.schemas.agent import (
    Claim,
    CriticResult,
    Evidence,
    Report,
    ResearchPlan,
    Source,
    SubQuestion,
)


@pytest.fixture
def mock_persistence_service():
    with patch("app.graph.nodes.persistence_service") as mock_ps:
        mock_ps.save_plan = AsyncMock()
        mock_ps.save_sources = AsyncMock()
        mock_ps.save_evidence = AsyncMock()
        mock_ps.save_claims = AsyncMock()
        mock_ps.save_critic_result = AsyncMock()
        mock_ps.save_agent_run = AsyncMock()
        yield mock_ps


@pytest.fixture
def mock_agents():
    with (
        patch("app.graph.nodes.planner_agent") as planner,
        patch("app.graph.nodes.web_research_agent") as web_research,
        patch("app.graph.nodes.source_ranker") as source_ranker,
        patch("app.graph.nodes.evidence_extractor") as evidence_extractor,
        patch("app.graph.nodes.synthesis_agent") as synthesis,
        patch("app.graph.nodes.critic_agent") as critic,
        patch("app.graph.nodes.writer_agent") as writer,
    ):
        # Setup mock returns
        sub_q_id = uuid.uuid4()
        planner.run = AsyncMock(
            return_value=ResearchPlan(
                sub_questions=[
                    SubQuestion(id=str(sub_q_id), question="Test sub Q1?", research_type="web")
                ]
            )
        )

        source1 = Source(
            id=str(uuid.uuid4()),
            task_id=str(sub_q_id),  # Must match sub-question id for task-aware routing
            title="Test Source",
            url="https://test.com",
            content="Test content",
            relevance_score=0.9,
        )
        web_research.run = AsyncMock(return_value=[source1])
        source_ranker.run = AsyncMock()

        evidence1 = Evidence(
            id=str(uuid.uuid4()),
            source_id=source1.id,
            sub_question_id=str(uuid.uuid4()),
            snippet="Test evidence",
        )
        evidence_extractor.run = AsyncMock(return_value=[evidence1])

        claim1 = Claim(
            id=str(uuid.uuid4()),
            statement="Test claim",
            evidence_ids=[evidence1.id],
            verification_status="pending",
        )
        synthesis.run = AsyncMock(return_value=[claim1])

        critic.run = AsyncMock(
            return_value=CriticResult(
                claims=[
                    Claim(
                        id=claim1.id,
                        statement="Test claim",
                        evidence_ids=[evidence1.id],
                        verification_status="verified",
                        critic_notes="Verified fine",
                    )
                ]
            )
        )

        writer.run = AsyncMock(
            return_value=Report(
                markdown="# Test Report\n\nContent here.",
                citation_map={"[1]": str(source1.id)},
                total_citations=1,
                word_count=100,
                section_count=2,
            )
        )

        yield {
            "planner": planner,
            "web_research": web_research,
            "source_ranker": source_ranker,
            "evidence_extractor": evidence_extractor,
            "synthesis": synthesis,
            "critic": critic,
            "writer": writer,
        }


@pytest.mark.asyncio
async def test_research_graph_success_path(mock_persistence_service, mock_agents):
    """Test the complete happy path of the research graph."""
    session_id = str(uuid.uuid4())
    initial_state = {
        "session_id": session_id,
        "research_question": "What is testing?",
        "research_plan": None,
        "sources": [],
        "evidence_items": [],
        "claims": [],
        "critic_result": None,
        "critic_iterations": 0,
        "report": None,
    }

    final_state = await research_graph.ainvoke(initial_state)

    # Verify state updates
    assert final_state["research_plan"] is not None
    assert len(final_state["sources"]) == 1
    assert len(final_state["evidence_items"]) == 1
    assert len(final_state["claims"]) == 1
    assert final_state["critic_result"] is not None
    assert final_state["report"] is not None
    assert final_state["report"].markdown.startswith("# Test Report")

    # Verify persistence was called
    mock_persistence_service.save_plan.assert_called_once()
    mock_persistence_service.save_sources.assert_called_once()
    mock_persistence_service.save_evidence.assert_called_once()
    mock_persistence_service.save_claims.assert_called_once()
    mock_persistence_service.save_critic_result.assert_called_once()


@pytest.mark.asyncio
async def test_research_graph_critic_loop(mock_persistence_service, mock_agents):
    """Test that the graph loops when critic rejects claims."""
    # First time: Reject. Second time: Verify
    call_count = 0

    async def mock_critic_run(claims, evidence_items, **kwargs):
        nonlocal call_count
        call_count += 1

        status = "unverified" if call_count == 1 else "verified"
        return CriticResult(
            claims=[
                Claim(
                    id=str(uuid.uuid4()),
                    statement="Test claim",
                    evidence_ids=[],
                    verification_status=status,
                    critic_notes="Notes",
                )
            ]
        )

    mock_agents["critic"].run.side_effect = mock_critic_run

    session_id = str(uuid.uuid4())
    initial_state = {
        "session_id": session_id,
        "research_question": "What is testing?",
        "research_plan": None,
        "sources": [],
        "evidence_items": [],
        "claims": [],
        "critic_result": None,
        "critic_iterations": 0,
        "report": None,
    }

    final_state = await research_graph.ainvoke(initial_state)

    # Should have looped
    assert final_state["critic_iterations"] == 2
    assert mock_agents["critic"].run.call_count == 2
    # It loops back to plan_research because logic says so, or it loops back to synthesis?
    # Wait, in edges.py: `if all verified or max_iterations: return "write_report" else: return "synthesize_claims" or something else?`
    # Let's verify the iterations actually bumped
