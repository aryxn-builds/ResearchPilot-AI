from __future__ import annotations

from typing import TypeVar
import asyncio

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

        Permanent errors (e.g. decommissioned model, 404 model-not-found, 401 unauthorized,
        402 insufficient credits, 403 forbidden) should not be retried on the same provider.
        We record the failure so subsequent calls in the session skip the broken provider entirely.
        """
        import re

        err_str = str(e).lower()

        # Tool Calling / Parsing / Validation errors are prompt/schema issues, not provider misconfigurations
        if "tool_use_failed" in err_str or "parse" in err_str or "validation" in err_str or "json" in err_str:
            return False

        # 429 / Rate Limit / Resource Exhausted handling
        # Standard rate limits are transient; project daily quotas (e.g. 500 RPD) are permanent for the day
        if (
            re.search(r"\b429\b", err_str)
            or "rate_limit" in err_str
            or "rate limit" in err_str
            or "resource_exhausted" in err_str
        ):
            if "generaterequestsperday" in err_str or "daily" in err_str:
                return True
            return False

        # Model decommissioned / deprecated / unsupported
        if (
            "decommissioned" in err_str
            or "model_decommissioned" in err_str
            or "deprecated" in err_str
            or "not supported" in err_str
            or "unsupported model" in err_str
            or "invalid model" in err_str
        ):
            return True

        # HTTP 404 / model not found patterns
        if (
            re.search(r"\b404\b", err_str)
            or "not_found" in err_str
            or "does not exist" in err_str
            or "no endpoints found" in err_str
        ):
            return True

        # Auth / Permission errors
        if (
            re.search(r"\b401\b", err_str)
            or "unauthorized" in err_str
            or "invalid_api_key" in err_str
            or re.search(r"\b403\b", err_str)
            or "forbidden" in err_str
        ):
            return True

        # Billing / Quota credit errors
        if (
            re.search(r"\b402\b", err_str)
            or "insufficient_quota" in err_str
            or "insufficient credits" in err_str
        ):
            return True

        # Project-level Daily Quota exhaustion (e.g. Gemini 500 RPD reached)
        if "generaterequestsperday" in err_str or "daily" in err_str:
            return True

        return False

    async def _sleep_backoff(self, attempt: int, error: Exception | None = None) -> None:
        """Sleep with exponential backoff and jitter if configured, respecting test overrides and retry-after headers."""
        import random
        import re

        base_delay = getattr(settings, "LLM_RETRY_BASE_DELAY", 0.5)
        if base_delay <= 0:
            return

        jitter = random.uniform(0.8, 1.2)
        sleep_time = min(5.0, base_delay * (2 ** attempt) * jitter)

        if error:
            err_str = str(error)
            # Check for explicit delay message e.g. "Please try again in 8.76s" or "retry in 42s"
            match = re.search(r"(?:try again in|retry in|retrydelay':\s*')([\d\.]+)", err_str, re.IGNORECASE)
            if match:
                try:
                    explicit_delay = float(match.group(1))
                    # Sleep at least the required delay, capped at 15s
                    sleep_time = min(15.0, max(sleep_time, explicit_delay + 0.5))
                except ValueError:
                    pass
            elif "429" in err_str or "rate limit" in err_str.lower():
                # Generic 429 without explicit delay: back off more generously (min 3s) to replenish token buckets
                sleep_time = min(15.0, max(3.0, sleep_time))

        logger.info("llm_retry_backoff", sleep_seconds=round(sleep_time, 3), attempt=attempt)
        await asyncio.sleep(sleep_time)

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
            for attempt in range(3):
                try:
                    model = self.gemini.with_structured_output(schema)
                    result = await model.ainvoke(messages, config=config)
                    if result:
                        return result
                except ValidationError as e:
                    logger.error("Primary LLM provider (Gemini) returned invalid schema", error=str(e), attempt=attempt)
                    if attempt == 2:
                        raise
                except Exception as e:
                    if self._is_permanent_error(e):
                        logger.error(
                            "Primary LLM provider (Gemini) has permanent error / daily quota exhaustion — "
                            "failing fast to fallback provider for the rest of this session",
                            error=str(e),
                        )
                        self._gemini_permanent_fail = True
                        break
                    else:
                        logger.warning("Primary LLM provider (Gemini) failed", error=str(e), attempt=attempt)
                        if attempt == 2:
                            break
                        await self._sleep_backoff(attempt, e)

        # 2. Fallback: Groq
        if not self._groq_permanent_fail:
            for attempt in range(3):
                try:
                    model = self.groq.with_structured_output(schema)
                    result = await model.ainvoke(messages, config=config)
                    if result:
                        return result
                except ValidationError as e:
                    logger.error("Fallback LLM provider (Groq) returned invalid schema", error=str(e), attempt=attempt)
                    if attempt == 2:
                        raise
                except Exception as e:
                    if self._is_permanent_error(e):
                        logger.error(
                            "Fallback LLM provider (Groq) has permanent error — "
                            "failing fast to secondary fallback for the rest of this session",
                            error=str(e),
                        )
                        self._groq_permanent_fail = True
                        break
                    else:
                        logger.warning("Fallback LLM provider (Groq) failed", error=str(e), attempt=attempt)
                        if attempt == 2:
                            break
                        await self._sleep_backoff(attempt, e)

        # 3. Secondary Fallback: OpenRouter
        if self.openrouter and not self._openrouter_permanent_fail:
            for attempt in range(3):
                try:
                    model = self.openrouter.with_structured_output(schema)
                    result = await model.ainvoke(messages, config=config)
                    if result:
                        return result
                except ValidationError as e:
                    logger.error(
                        "Secondary fallback LLM provider (OpenRouter) returned invalid schema",
                        error=str(e),
                        attempt=attempt
                    )
                    if attempt == 2:
                        raise
                except Exception as e:
                    if self._is_permanent_error(e):
                        logger.error(
                            "Secondary fallback LLM provider (OpenRouter) has permanent error",
                            error=str(e),
                        )
                        self._openrouter_permanent_fail = True
                        break
                    else:
                        logger.warning("Secondary fallback LLM provider (OpenRouter) failed", error=str(e), attempt=attempt)
                        if attempt == 2:
                            break
                        await self._sleep_backoff(attempt, e)

        # Exhausted
        logger.error("All LLM providers exhausted")
        raise ProviderExhaustedError("All LLM providers failed to generate a response.")

    async def validate_provider_health(self, provider_name: str) -> dict:
        """Lightweight health check validating that a provider is reachable and can perform structured output."""
        from pydantic import Field

        class HealthCheckSchema(BaseModel):
            status: str = Field(description="Health status, should be 'healthy'")

        result = {
            "provider": provider_name,
            "healthy": False,
            "model": None,
            "error": None,
        }

        try:
            if provider_name == "gemini":
                result["model"] = settings.GEMINI_MODEL
                if not settings.GEMINI_API_KEY:
                    result["error"] = "API key not configured"
                    return result
                model = self.gemini.with_structured_output(HealthCheckSchema)
            elif provider_name == "groq":
                result["model"] = settings.GROQ_MODEL
                if not settings.GROQ_API_KEY:
                    result["error"] = "API key not configured"
                    return result
                model = self.groq.with_structured_output(HealthCheckSchema)
            elif provider_name == "openrouter":
                result["model"] = settings.OPENROUTER_MODEL
                if not settings.OPENROUTER_API_KEY:
                    result["error"] = "API key not configured"
                    return result
                if not self.openrouter:
                    self.openrouter = get_openrouter_model()
                model = self.openrouter.with_structured_output(HealthCheckSchema)
            else:
                result["error"] = f"Unknown provider: {provider_name}"
                return result

            test_prompt = "Record health check status='healthy'."
            resp = await model.ainvoke(test_prompt)
            if resp and resp.status:
                result["healthy"] = True
            else:
                result["error"] = "No response from model"
        except Exception as e:
            result["error"] = str(e)

        return result

