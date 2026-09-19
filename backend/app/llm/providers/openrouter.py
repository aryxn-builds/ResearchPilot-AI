from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings


def get_openrouter_model() -> ChatOpenAI:
    """Initialize and return the OpenRouter chat model.
    OpenRouter provides an OpenAI-compatible API.
    """
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not configured")

    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        model=settings.OPENROUTER_MODEL,
        api_key=SecretStr(settings.OPENROUTER_API_KEY),
        temperature=0.0,
        max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        max_retries=settings.LLM_RETRY_ATTEMPTS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        default_headers={
            "HTTP-Referer": "https://github.com/ResearchPilot/researchpilot",
            "X-Title": "ResearchPilot AI",
        },
    )
