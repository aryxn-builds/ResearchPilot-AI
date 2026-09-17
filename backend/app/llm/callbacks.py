import time
from typing import Any
from uuid import UUID

import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from app.services.persistence import PersistenceService

logger = structlog.get_logger(__name__)


class AsyncAgentRunCallbackHandler(AsyncCallbackHandler):
    """Callback Handler that logs agent runs (LLM calls) to the database."""

    def __init__(self, session_id: str, agent_name: str, persistence: PersistenceService):
        self.session_id = session_id
        self.agent_name = agent_name
        self.persistence = persistence
        self.start_times: dict[UUID, float] = {}

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM starts."""
        self.start_times[run_id] = time.time()

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM ends running."""
        end_time = time.time()
        start_time = self.start_times.pop(run_id, end_time)
        duration_ms = int((end_time - start_time) * 1000)

        # Try to extract tokens if available
        tokens_used = None
        if response.llm_output and "token_usage" in response.llm_output:
            tokens_used = response.llm_output["token_usage"].get("total_tokens")

        # Basic summary of output to prevent saving massive logs/thoughts
        output_summary = {"generations_count": len(response.generations)}

        # The provider is usually in kwargs or we could just capture it from the LLMRouter
        # but Langchain callbacks don't easily give the exact provider name.
        # We will log the model name if available.
        llm_provider_used = "unknown"
        if response.llm_output and "model_name" in response.llm_output:
            llm_provider_used = response.llm_output["model_name"]

        await self.persistence.save_agent_run(
            session_id=self.session_id,
            agent_name=self.agent_name,
            status="completed",
            input_summary={"status": "invoked"},
            output_summary=output_summary,
            llm_provider_used=llm_provider_used,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM errors."""
        end_time = time.time()
        start_time = self.start_times.pop(run_id, end_time)
        duration_ms = int((end_time - start_time) * 1000)

        await self.persistence.save_agent_run(
            session_id=self.session_id,
            agent_name=self.agent_name,
            status="failed",
            input_summary={"status": "invoked"},
            error_message=str(error),
            duration_ms=duration_ms,
        )
