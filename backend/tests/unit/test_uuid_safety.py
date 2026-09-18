import pytest
import uuid
from pydantic import BaseModel, Field

from app.schemas.agent import ResearchPlan, SubQuestion, CriticResult, Claim
from app.agents.planner import PlannerAgent
from app.agents.synthesis import SynthesisAgent

class MockLLMRouter:
    def __init__(self, mock_response: BaseModel):
        self.mock_response = mock_response

    async def generate_structured(self, messages, response_schema, **kwargs):
        return self.mock_response

@pytest.mark.asyncio
async def test_planner_agent_overwrites_llm_uuid():
    # LLM returns a hallucinated/invalid string ID
    mock_plan = ResearchPlan(
        sub_questions=[
            SubQuestion(
                id="not-a-real-uuid",
                question="What is Python 3.12?",
                research_type="web"
            )
        ]
    )
    
    router = MockLLMRouter(mock_plan)
    agent = PlannerAgent(llm_router=router)
    
    plan = await agent.run("Tell me about Python 3.12")
    
    # Assert that it's no longer 'not-a-real-uuid'
    sq = plan.sub_questions[0]
    assert sq.id != "not-a-real-uuid"
    
    # Assert that it's a valid UUID
    try:
        parsed_uuid = uuid.UUID(sq.id)
        assert str(parsed_uuid) == sq.id
    except ValueError:
        pytest.fail("Planner did not assign a valid UUID")

@pytest.mark.asyncio
async def test_synthesis_agent_overwrites_llm_uuid():
    # LLM returns a hallucinated/invalid string ID
    mock_result = CriticResult(
        claims=[
            Claim(
                id="fake-claim-uuid-x",
                statement="Python is fast.",
                evidence_ids=["fake-evidence-id"],
                verification_status="verified",
                critic_notes="Looks good"
            )
        ]
    )
    
    router = MockLLMRouter(mock_result)
    agent = SynthesisAgent(llm_router=router)
    
    from app.schemas.agent import Evidence
    
    dummy_evidence = [
        Evidence(id="x", sub_question_id="y", source_id="z", snippet="dummy")
    ]
    claims = await agent.run(dummy_evidence)
    
    # Assert that it's no longer 'fake-claim-uuid-x'
    claim = claims[0]
    assert claim.id != "fake-claim-uuid-x"
    
    # Assert that it's a valid UUID
    try:
        parsed_uuid = uuid.UUID(claim.id)
        assert str(parsed_uuid) == claim.id
    except ValueError:
        pytest.fail("SynthesisAgent did not assign a valid UUID")
