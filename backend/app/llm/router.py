from __future__ import annotations

from typing import TypeVar

import structlog
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

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

    # Track permanent provider failures within this router instance's lifetime.
    # A 404 model-not-found error is permanent — the model won't appear mid-session.
    # Marking a provider failed avoids N repeated 404 roundtrips per pipeline run.
    _PERMANENT_ERROR_CODES = {404, 400}

    def __init__(self) -> None:
        self.gemini = get_gemini_model()
        self.groq = get_groq_model()
        self.openrouter = None
        self._gemini_permanent_fail = False
        self._groq_permanent_fail = False
        self._openrouter_permanent_fail = False

        if settings.OPENROUTER_API_KEY:
            self.openrouter = get_openrouter_model()

    @staticmethod
    def _is_permanent_error(e: Exception) -> bool:
        """Return True if the error indicates a permanent provider misconfiguration.

        Permanent errors (e.g. 404 model-not-found, 400 bad-request) should not
        be retried on the same provider and do not warrant re-raising immediately —
        we still want to try the next fallback provider. However we record the failure
        so subsequent calls in the same session skip the broken provider entirely.
        """
        err_str = str(e).lower()
        # HTTP 404 / model not found / deprecated model patterns
        if "404" in err_str or "not_found" in err_str or "does not exist" in err_str:
            return True
        # HTTP 400 / bad request (often a model config issue)
        if "400" in err_str and "bad request" in err_str:
            return True
        return False

    async def generate_structured(
        self, messages: list[BaseMessage] | str, schema: type[T], callbacks: list | None = None
    ) -> T:
        """Generate a structured response using the provider fallback chain.

        Args:
            messages: The prompt or list of messages.
            schema: The Pydantic model class to extract.
            callbacks: Optional LangChain callbacks.

        Returns:
            An instance of the requested Pydantic model.

        Raises:
            ProviderExhaustedError: If all providers fail.
            ValidationError: If the LLM generates a response that fails schema validation
                (not cascaded to next provider — schema errors are prompt issues).
        """
        config = {"callbacks": callbacks} if callbacks else None

        # 1. Primary: Gemini
        if not self._gemini_permanent_fail:
            try:
                model = self.gemini.with_structured_output(schema)
                result = await model.ainvoke(messages, config=config)
                if result:
                    return result
            except ValidationError as e:
                logger.error("Primary LLM provider (Gemini) returned invalid schema", error=str(e))
                raise
            except Exception as e:
                if self._is_permanent_error(e):
                    logger.error(
                        "Primary LLM provider (Gemini) has permanent configuration error — "
                        "skipping for the rest of this session",
                        error=str(e),
                    )
                    self._gemini_permanent_fail = True
                else:
                    logger.warning("Primary LLM provider (Gemini) failed", error=str(e))

        # 2. Fallback: Groq
        if not self._groq_permanent_fail:
            try:
                model = self.groq.with_structured_output(schema)
                result = await model.ainvoke(messages, config=config)
                if result:
                    return result
            except ValidationError as e:
                logger.error("Fallback LLM provider (Groq) returned invalid schema", error=str(e))
                raise
            except Exception as e:
                if self._is_permanent_error(e):
                    logger.error(
                        "Fallback LLM provider (Groq) has permanent configuration error — "
                        "skipping for the rest of this session",
                        error=str(e),
                    )
                    self._groq_permanent_fail = True
                else:
                    logger.warning("Fallback LLM provider (Groq) failed", error=str(e))

        # 3. Secondary Fallback: OpenRouter
        if self.openrouter and not self._openrouter_permanent_fail:
            try:
                model = self.openrouter.with_structured_output(schema)
                result = await model.ainvoke(messages, config=config)
                if result:
                    return result
            except ValidationError as e:
                logger.error(
                    "Secondary fallback LLM provider (OpenRouter) returned invalid schema",
                    error=str(e),
                )
                raise
            except Exception as e:
                if self._is_permanent_error(e):
                    logger.error(
                        "Secondary fallback LLM provider (OpenRouter) has permanent configuration error",
                        error=str(e),
                    )
                    self._openrouter_permanent_fail = True
                else:
                    logger.warning("Secondary fallback LLM provider (OpenRouter) failed", error=str(e))

        # Exhausted
        logger.error("All LLM providers exhausted")
        raise ProviderExhaustedError("All LLM providers failed to generate a response.")

