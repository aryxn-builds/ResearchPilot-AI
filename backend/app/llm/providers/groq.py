from __future__ import annotations

from langchain_groq import ChatGroq
from pydantic import SecretStr

from app.core.config import settings


def get_groq_model() -> ChatGroq:
    """Initialize and return the Groq chat model."""
    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=SecretStr(settings.GROQ_API_KEY),
        temperature=0.0,
        max_retries=settings.LLM_RETRY_ATTEMPTS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
