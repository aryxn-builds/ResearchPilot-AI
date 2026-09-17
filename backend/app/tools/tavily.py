from __future__ import annotations

from urllib.parse import urlparse
from uuid import uuid4

import structlog
from tavily import AsyncTavilyClient

from app.core.config import settings
from app.schemas.agent import Source, SubQuestion

logger = structlog.get_logger(__name__)


class TavilyTool:
    """Wrapper for the Tavily search API.

    Implements graceful degradation: failures return empty lists rather than
    crashing the research session (Rule A-04, Data Flow).
    """

    def __init__(self) -> None:
        # Initialize the async client
        self.client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)

    async def search(self, sub_question: SubQuestion) -> list[Source]:
        """Perform a web search and extract full content.

        Args:
            sub_question: The decomposed question to research.

        Returns:
            A list of Source objects with extracted content.
        """
        try:
            logger.info("Executing Tavily search", query=sub_question.question)
            response = await self.client.search(
                query=sub_question.question,
                search_depth=settings.TAVILY_SEARCH_DEPTH,
                max_results=settings.TAVILY_MAX_RESULTS,
                include_raw_content=True,
                include_answer=False,
            )

            sources: list[Source] = []
            for result in response.get("results", []):
                # Fallback to snippet if raw_content is missing
                content = result.get("raw_content") or result.get("content", "")
                if not content:
                    continue

                # Truncate content to roughly the max token limit (approx 4 chars per token)
                max_chars = settings.RESEARCH_MAX_SOURCE_CONTENT_TOKENS * 4
                if len(content) > max_chars:
                    content = content[:max_chars] + "... [truncated]"

                domain = None
                try:
                    parsed_url = urlparse(result.get("url", ""))
                    domain = parsed_url.netloc
                except Exception:
                    pass

                sources.append(
                    Source(
                        id=uuid4(),
                        task_id=sub_question.id,
                        url=result.get("url", ""),
                        title=result.get("title", ""),
                        content=content,
                        domain=domain,
                        published_date=result.get("published_date"),
                    )
                )

            return sources

        except Exception as e:
            logger.error("Tavily search failed", error=str(e), query=sub_question.question)
            return []  # Graceful failure
