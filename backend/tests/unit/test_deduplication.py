import uuid
from unittest.mock import patch

import pytest

from app.graph.nodes import rank_sources
from app.graph.state import ResearchState
from app.schemas.agent import Source


@pytest.mark.asyncio
async def test_rank_sources_deduplication():
    # Setup state with duplicate URLs
    session_id = str(uuid.uuid4())
    s1 = Source(
        id=uuid.uuid4(),
        url="https://example.com/page1",
        title="Page 1",
        content="Test content 1",
        relevance_score=0.9,
    )
    s2 = Source(
        id=uuid.uuid4(),
        url="https://example.com/page1",  # Duplicate URL
        title="Page 1 duplicate",
        content="Test content 2",
        relevance_score=0.8,
    )
    s3 = Source(
        id=uuid.uuid4(),
        url="https://example.com/page2",
        title="Page 2",
        content="Test content 3",
        relevance_score=0.7,
    )

    state: ResearchState = {
        "session_id": session_id,
        "research_question": "Test?",
        "research_plan": None,
        "sources": [s1, s2, s3],
        "evidence_items": [],
        "claims": [],
        "critic_result": None,
        "critic_iterations": 0,
        "report": None,
    }

    with (
        patch("app.graph.nodes.source_ranker.run") as mock_ranker_run,
        patch("app.graph.nodes.persistence_service.save_sources") as mock_save,
    ):
        mock_ranker_run.return_value = None

        result = await rank_sources(state, {})

        # Should have deduplicated s2, leaving s1 and s3
        returned_sources = result["sources"]["items"]
        assert len(returned_sources) == 2

        urls = [s.url for s in returned_sources]
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls

        # Verify persistence was called with deduplicated sources
        mock_save.assert_called_once()
        saved_sources = mock_save.call_args[0][1]
        assert len(saved_sources) == 2
