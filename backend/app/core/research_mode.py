"""Resolve research mode without a provider request."""

import re
from contextvars import ContextVar
from typing import Literal

ExecutionMode = Literal["fast", "deep"]
fast_research: ContextVar[bool] = ContextVar("fast_research", default=False)
research_session: ContextVar[str | None] = ContextVar("research_session", default=None)


def resolve_mode(question: str, requested: str = "deep") -> ExecutionMode:
    """Auto selects Fast only for recognizable, narrowly scoped questions."""
    if requested == "fast":
        return "fast"
    if requested != "auto":
        return "deep"
    normalized = " ".join(question.lower().split()).rstrip("?.")
    if len(normalized.split()) > 18 or re.search(
        r"[,;?]|\b(?:across|impacts?|effects?|future|history|and also|all|everything|comprehensive)\b", normalized
    ):
        return "deep"
    if re.fullmatch(r"(?:what (?:is|are)|define) (?:[\w.+-]+ ){0,5}[\w.+-]+", normalized):
        return "fast"
    if re.fullmatch(r"compare (?:[\w.+-]+ ){0,3}[\w.+-]+ (?:and|vs\.?) (?:[\w.+-]+ ){0,3}[\w.+-]+", normalized):
        return "fast"
    return "deep"
