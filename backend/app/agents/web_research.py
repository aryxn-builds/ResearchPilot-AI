from __future__ import annotations

import structlog

from app.schemas.agent import Source, SubQuestion
from app.tools.tavily import TavilyTool

logger = structlog.get_logger(__name__)


class WebResearchAgent:
    """Agent responsible for gathering sources from the web using Tavily."""

    def __init__(self, tavily_tool: TavilyTool) -> None:
        self.tavily_tool = tavily_tool

    async def run(self, sub_question: SubQuestion) -> list[Source]:
        """Execute the research for a single sub-question.

        Args:
            sub_question: The decomposed SubQuestion.

        Returns:
            A list of gathered Sources.
        """
        logger.info("WebResearchAgent starting", question=sub_question.question)

        if sub_question.research_type != "web":
            logger.warning(
                "WebResearchAgent received non-web question", type=sub_question.research_type
            )
            return []

        # TAVILY SEARCH (which handles extracting content too)
        sources = await self.tavily_tool.search(sub_question)

        logger.info("WebResearchAgent completed", num_sources=len(sources))
        return sources
