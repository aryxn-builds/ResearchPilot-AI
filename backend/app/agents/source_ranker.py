from __future__ import annotations

import structlog

from app.schemas.agent import Source

logger = structlog.get_logger(__name__)


class SourceRanker:
    """Agent responsible for scoring and ranking gathered sources.

    Currently uses simple heuristics as per MVP specification.
    """

    def __init__(self) -> None:
        pass

    async def run(self, sources: list[Source]) -> list[Source]:
        """Score and flag sources.

        Args:
            sources: List of gathered sources.

        Returns:
            The same list of sources with updated scores and flags.
        """
        logger.info("SourceRanker starting", num_sources=len(sources))

        for source in sources:
            score = 0.5  # Baseline

            # Simple URL heuristics
            url_lower = source.url.lower()
            if ".edu" in url_lower or ".gov" in url_lower or ".ac." in url_lower:
                score += 0.3
            elif ".org" in url_lower:
                score += 0.1

            # Content length heuristic
            if len(source.content) > 500:
                score += 0.1

            # Cap at 1.0
            source.credibility_score = min(score, 1.0)

            # Flag low credibility
            if source.credibility_score < 0.3:
                source.is_flagged = True

            # Relevance score (heuristic placeholder for MVP)
            source.relevance_score = 0.8

        # Sort by credibility descending
        sources.sort(key=lambda s: s.credibility_score, reverse=True)

        logger.info("SourceRanker completed")
        return sources
