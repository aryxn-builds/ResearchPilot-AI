from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from app.core.config import settings


def get_gemini_model() -> ChatGoogleGenerativeAI:
    """Initialize and return the Gemini chat model."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=SecretStr(settings.GEMINI_API_KEY),
        temperature=0.0,
        max_retries=settings.LLM_RETRY_ATTEMPTS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
