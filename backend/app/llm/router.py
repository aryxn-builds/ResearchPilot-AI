from __future__ import annotations

from typing import TypeVar

import structlog
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import ProviderExhaustedError
from app.llm.providers.gemini import get_gemini_model
from app.llm.providers.groq import get_groq_model
from app.llm.providers.openrouter import get_openrouter_model

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMRouter:
    """Central router for all LLM calls.
    
    Implements Provider Abstraction (Rule A-03) and Fallback Routing.
    """

    def __init__(self) -> None:
        self.gemini = get_gemini_model()
        self.groq = get_groq_model()
        self.openrouter = None
        
        if settings.OPENROUTER_API_KEY:
            self.openrouter = get_openrouter_model()

    async def generate_structured(self, messages: list[BaseMessage] | str, schema: type[T]) -> T:
        """Generate a structured response using the provider fallback chain.
        
        Args:
            messages: The prompt or list of messages.
            schema: The Pydantic model class to extract.
            
        Returns:
            An instance of the requested Pydantic model.
            
        Raises:
            ProviderExhaustedError: If all providers fail.
        """
        # 1. Primary: Gemini
        try:
            model = self.gemini.with_structured_output(schema)
            result = await model.ainvoke(messages)
            if result:
                return result
        except Exception as e:
            logger.warning("Primary LLM provider (Gemini) failed", error=str(e))

        # 2. Fallback: Groq
        try:
            model = self.groq.with_structured_output(schema)
            result = await model.ainvoke(messages)
            if result:
                return result
        except Exception as e:
            logger.warning("Fallback LLM provider (Groq) failed", error=str(e))

        # 3. Secondary Fallback: OpenRouter
        if self.openrouter:
            try:
                model = self.openrouter.with_structured_output(schema)
                result = await model.ainvoke(messages)
                if result:
                    return result
            except Exception as e:
                logger.warning("Secondary fallback LLM provider (OpenRouter) failed", error=str(e))

        # Exhausted
        logger.error("All LLM providers exhausted")
        raise ProviderExhaustedError("All LLM providers failed to generate a response.")
