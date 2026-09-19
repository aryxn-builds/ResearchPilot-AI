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
        input_tokens = None
        output_tokens = None
        if response.llm_output and "token_usage" in response.llm_output:
            tokens_used = response.llm_output["token_usage"].get("total_tokens")
            input_tokens = response.llm_output["token_usage"].get("prompt_tokens")
            output_tokens = response.llm_output["token_usage"].get("completion_tokens")

        llm_provider_used = "unknown"
        if response.llm_output and "model_name" in response.llm_output:
            llm_provider_used = response.llm_output["model_name"]

        # Also check generations for modern LangChain message metadata
        if response.generations and response.generations[0]:
            first_gen = response.generations[0][0]
            if hasattr(first_gen, "message"):
                usage = getattr(first_gen.message, "usage_metadata", None)
                if isinstance(usage, dict):
                    if tokens_used is None:
                        tokens_used = usage.get("total_tokens")
                    if input_tokens is None:
                        input_tokens = usage.get("input_tokens")
                    if output_tokens is None:
                        output_tokens = usage.get("output_tokens")
                resp_meta = getattr(first_gen.message, "response_metadata", None)
                if isinstance(resp_meta, dict) and llm_provider_used == "unknown":
                    llm_provider_used = (
                        resp_meta.get("model_name")
                        or resp_meta.get("model_provider")
                        or "unknown"
                    )

        # Basic summary of output including token breakdown
        output_summary = {
            "generations_count": len(response.generations),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": tokens_used,
            "model_name": llm_provider_used,
        }

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
