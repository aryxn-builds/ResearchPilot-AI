from __future__ import annotations

import asyncio
import re
from time import monotonic, perf_counter
from typing import TypeVar

import structlog
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import ProviderExhaustedError
from app.core.research_mode import fast_research, research_session
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

    async def _sleep_backoff(self, attempt: int) -> None:
        """Wait briefly before retrying a transient non-quota failure."""
        import random

        if settings.LLM_RETRY_BASE_DELAY <= 0:
            return
        delay = min(5.0, settings.LLM_RETRY_BASE_DELAY * (2 ** attempt) * random.uniform(0.8, 1.2))
        logger.info("llm_retry_backoff", session_id=research_session.get(),
                    sleep_seconds=round(delay, 3), attempt=attempt + 1)
        await asyncio.sleep(delay)

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
                (in Deep Research, not cascaded to next provider — schema errors are prompt issues).
        """
        config = {"callbacks": callbacks} if callbacks else None
        fast = fast_research.get()
        timeout = settings.FAST_LLM_TIMEOUT_SECONDS if fast else settings.LLM_TIMEOUT_SECONDS
        attempts = 1 if fast else max(1, min(3, settings.LLM_RETRY_ATTEMPTS))
        cooldowns = self.__dict__.setdefault("_cooldowns", {})
        providers = ["gemini", "groq", "openrouter"]
        primary = settings.PRIMARY_LLM_PROVIDER
        providers.remove(primary)
        providers.insert(0, primary)
        for name in providers:
            client = getattr(self, name)
            failed_flag = f"_{name}_permanent_fail"
            if client is None or getattr(self, failed_flag) or cooldowns.get(name, 0) > monotonic():
                continue
            for attempt in range(attempts):
                if cooldowns.get(name, 0) > monotonic():
                    break
                started = perf_counter()
                outcome = "failed"
                try:
                    selected = client
                    if fast:
                        # Bind the token budget on the chat model before building its schema wrapper.
                        selected = client.model_copy(update={
                            "max_output_tokens" if name == "gemini" else "max_tokens":
                                settings.FAST_LLM_OUTPUT_TOKENS,
                        })
                    model = selected.with_structured_output(schema)
                    async with asyncio.timeout(timeout):
                        result = await model.ainvoke(messages, config=config)
                    if result is None:
                        raise ValueError("Empty structured output")
                    parsed = schema.model_validate(result)
                    outcome = "success"
                    return parsed
                except Exception as error:
                    if isinstance(error, ValidationError) and not fast and attempt + 1 == attempts:
                        outcome = "invalid_output"
                        raise
                    message = str(error).lower()
                    daily = bool(re.search(
                        r"generaterequestsperday|tokensperday|tokens per day|requests per day|\btpd\b|\brpd\b|daily",
                        message,
                    ))
                    limited = bool(re.search(r"\b429\b|rate.limit|resource.exhausted", message))
                    if daily or limited:
                        outcome = "daily_quota" if daily else "rate_limit"
                        delay = 86400 if daily else settings.LLM_COOLDOWN_SECONDS
                        retry_after = re.search(r"(?:try again in|retry in)\s*([\d.]+)s", message)
                        if retry_after:
                            delay = max(delay, min(86400, float(retry_after.group(1))))
                        cooldowns[name] = monotonic() + delay
                        break
                    if self._is_permanent_error(error):
                        outcome = "permanent"
                        setattr(self, failed_flag, True)
                        break
                    if isinstance(error, TimeoutError):
                        outcome = "timeout"
                    elif isinstance(error, (ValidationError, ValueError)):
                        outcome = "invalid_output"
                    if attempt + 1 == attempts and outcome in {"timeout", "failed"}:
                        cooldowns[name] = monotonic() + settings.LLM_COOLDOWN_SECONDS
                finally:
                    logger.info(
                        "research_llm_attempt",
                        session_id=research_session.get(), provider=name, schema=schema.__name__,
                        attempt=attempt + 1, outcome=outcome,
                        duration_ms=round((perf_counter() - started) * 1000, 2),
                    )
                if attempt + 1 < attempts:
                    await self._sleep_backoff(attempt)
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
            async with asyncio.timeout(settings.FAST_LLM_TIMEOUT_SECONDS):
                resp = await model.ainvoke(test_prompt)
            if isinstance(resp, BaseModel):
                resp = resp.model_dump()
            if HealthCheckSchema.model_validate(resp).status == "healthy":
                result["healthy"] = True
            else:
                result["error"] = "No response from model"
        except Exception as e:
            result["error"] = str(e)

        return result

