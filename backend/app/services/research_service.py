"""ResearchService — orchestrates research session lifecycle.

Responsibilities:
  - Create and persist research sessions in the database.
  - Enqueue research jobs as asyncio Tasks (ADR-002 — MVP approach).
  - Cancel in-progress sessions.
  - Soft-delete completed/failed sessions.
  - Query session status and history.

AGENTS.md Rule A-01: This service is between the API layer and LangGraph.
It must NOT contain agent logic or call LLM directly.
The LangGraph graph (not yet implemented) will be triggered from here in Phase 1B.

Phase 1A: Database persistence methods are implemented.
          LangGraph invocation is a stub (raises NotImplementedError).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from uuid import UUID

import structlog

from app.core.config import settings
from app.core.database import get_service_client
from app.core.exceptions import (
    MaxSessionsReachedError,
    ResearchNotFoundError,
)
from app.graph.research_graph import research_graph
from app.graph.state import ResearchState
from app.schemas.research import ResearchConfig, ResearchSessionResponse, ResearchStatus

logger = structlog.get_logger(__name__)

# In-memory task registry: { session_id_str -> asyncio.Task }
# ADR-002: Tasks live only in the current process. Lost on restart.
_active_tasks: dict[str, asyncio.Task] = {}


class SessionEventBus:
    """In-memory pub-sub for SSE events."""
    
    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        if session_id not in self._queues:
            self._queues[session_id] = []
        q = asyncio.Queue()
        self._queues[session_id].append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        if session_id in self._queues:
            self._queues[session_id].remove(q)
            if not self._queues[session_id]:
                del self._queues[session_id]

    async def publish(self, session_id: str, event: str, data: dict) -> None:
        if session_id in self._queues:
            for q in self._queues[session_id]:
                await q.put((event, data))


event_bus = SessionEventBus()


class ResearchService:
    """Manages research session lifecycle from submission to completion.

    All database operations use the service role client (bypasses RLS)
    because agents write data on behalf of users, not as users.
    ADR-003: The service role key is backend-only.
    """

    async def create_session(
        self,
        user_id: UUID,
        question: str,
        config: ResearchConfig,
        idempotency_key: str | None = None,
    ) -> ResearchSessionResponse:
        """Create a new research session record in the database.

        Args:
            user_id: The authenticated user's UUID.
            question: The research question (already validated by API schema).
            config: Research configuration (max_iterations, source_types, etc.).
            idempotency_key: Optional client-provided key for deduplication.

        Returns:
            ResearchSessionResponse with the new session details.

        Raises:
            MaxSessionsReachedError: If the user has too many active sessions.
            SessionAlreadyExistsError: If idempotency_key was already used.
        """
        client = get_service_client()

        # Check active session count for this user
        active_count_result = (
            await client.table("research_sessions")
            .select("id", count="exact")
            .eq("user_id", str(user_id))
            .in_("status", ["pending", "planning", "researching", "verifying", "writing"])
            .is_("deleted_at", "null")
            .execute()
        )
        active_count = active_count_result.count or 0
        if active_count >= settings.RESEARCH_MAX_CONCURRENT_SESSIONS_PER_USER:
            raise MaxSessionsReachedError(settings.RESEARCH_MAX_CONCURRENT_SESSIONS_PER_USER)

        # Check idempotency key if provided
        if idempotency_key:
            existing = (
                await client.table("research_sessions")
                .select("id, status")
                .eq("user_id", str(user_id))
                .eq("idempotency_key", idempotency_key)
                .is_("deleted_at", "null")
                .execute()
            )
            if existing.data:
                # Return existing session (idempotent response)
                return await self.get_session(UUID(existing.data[0]["id"]), user_id)

        session_id = uuid.uuid4()
        now = datetime.now(tz=UTC).isoformat()

        row = {
            "id": str(session_id),
            "user_id": str(user_id),
            "research_question": question,
            "status": "pending",
            "config": config.model_dump(),
            "iteration_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        if idempotency_key:
            row["idempotency_key"] = idempotency_key

        result = await client.table("research_sessions").insert(row).execute()
        data = result.data[0]

        logger.info("research_session_created", session_id=str(session_id), user_id=str(user_id))

        return self._row_to_response(data)

    async def start_research_task(self, session_id: UUID, user_id: UUID) -> None:
        """Enqueue the research job as an asyncio background task.

        ADR-002: For MVP, research runs in-process. The LangGraph graph
        will be invoked from _run_research_graph() in Phase 1B.

        Args:
            session_id: The session to run research for.
            user_id: The owning user.
        """
        task = asyncio.create_task(
            self._run_research_graph(session_id, user_id),
            name=f"research-{session_id}",
        )
        _active_tasks[str(session_id)] = task
        task.add_done_callback(lambda t: _active_tasks.pop(str(session_id), None))
        logger.info("research_task_enqueued", session_id=str(session_id))

    async def _run_research_graph(self, session_id: UUID, user_id: UUID) -> None:
        """Execute the LangGraph research pipeline for a session."""
        try:
            session = await self.get_session(session_id, user_id)
            
            # Initial state
            state: ResearchState = {
                "research_question": session.question,
                "research_plan": None,
                "sources": [],
                "evidence_items": [],
                "claims": [],
                "critic_result": None,
                "critic_iterations": 0,
                "report_markdown": None,
            }

            await self._update_session_status(session_id, "planning")
            await event_bus.publish(str(session_id), "status_update", {"status": "planning"})
            
            # Run LangGraph streaming
            final_state = state
            async for s in research_graph.astream(state, stream_mode="updates"):
                node_name = list(s.keys())[0]
                # Merge state manually or let graph do it. `astream` returns partials,
                # but we can just use it to track progress. We'll get the final state later.
                
                if node_name == "plan_research":
                    await self._update_session_status(session_id, "researching")
                    await event_bus.publish(str(session_id), "status_update", {"status": "researching"})
                elif node_name == "extract_evidence":
                    await self._update_session_status(session_id, "verifying")
                    await event_bus.publish(str(session_id), "status_update", {"status": "verifying"})
                elif node_name == "critic_verify":
                    await self._update_session_status(session_id, "writing")
                    await event_bus.publish(str(session_id), "status_update", {"status": "writing"})

            # Graph finished, get final state
            final_state = await research_graph.ainvoke(state)
            
            # Save report to DB
            client = get_service_client()
            report_id = str(uuid.uuid4())
            now = datetime.now(tz=UTC).isoformat()
            
            # Check verified claims
            verified_count = 0
            if final_state.get("critic_result"):
                verified_count = len([c for c in final_state["critic_result"].claims if c.verification_status == "verified"])
                
            await client.table("research_reports").insert({
                "id": report_id,
                "session_id": str(session_id),
                "markdown_content": final_state.get("report_markdown", ""),
                "created_at": now,
            }).execute()

            # Update session
            await client.table("research_sessions").update({
                "status": "completed",
                "completed_at": now,
                "updated_at": now,
                "iteration_count": final_state.get("critic_iterations", 0),
                "total_claims": len(final_state.get("claims", [])),
                "verified_claims": verified_count,
            }).eq("id", str(session_id)).execute()

            await event_bus.publish(str(session_id), "done", {"status": "completed"})
            
        except asyncio.CancelledError:
            logger.info("Research task cancelled", session_id=str(session_id))
            await event_bus.publish(str(session_id), "error", {"message": "Task cancelled"})
        except Exception as e:
            logger.error("Research graph failed", session_id=str(session_id), error=str(e))
            await self._update_session_status(session_id, "failed", str(e))
            await event_bus.publish(str(session_id), "error", {"message": "Research pipeline failed"})

    async def get_session(self, session_id: UUID, user_id: UUID) -> ResearchSessionResponse:
        """Fetch a research session, enforcing user ownership.

        Args:
            session_id: The session UUID.
            user_id: The requesting user's UUID (for ownership check).

        Returns:
            ResearchSessionResponse.

        Raises:
            ResearchNotFoundError: If not found or belongs to another user.
        """
        client = get_service_client()
        result = (
            await client.table("research_sessions")
            .select("*")
            .eq("id", str(session_id))
            .eq("user_id", str(user_id))
            .is_("deleted_at", "null")
            .execute()
        )
        if not result.data:
            raise ResearchNotFoundError(str(session_id))

        return self._row_to_response(result.data[0])

    async def list_sessions(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: ResearchStatus | None = None,
    ) -> tuple[list[ResearchSessionResponse], int]:
        """List research sessions for a user with pagination.

        Args:
            user_id: The user's UUID.
            page: 1-indexed page number.
            page_size: Results per page (max 50).
            status: Optional status filter.

        Returns:
            Tuple of (sessions_list, total_count).
        """
        client = get_service_client()
        query = (
            client.table("research_sessions")
            .select("*", count="exact")
            .eq("user_id", str(user_id))
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
        )

        if status:
            query = query.eq("status", status)

        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        result = await query.execute()
        sessions = [self._row_to_response(row) for row in (result.data or [])]
        total = result.count or 0

        return sessions, total

    async def cancel_or_delete_session(
        self, session_id: UUID, user_id: UUID
    ) -> ResearchSessionResponse:
        """Cancel an in-progress session or soft-delete a completed one.

        Args:
            session_id: The session to cancel/delete.
            user_id: The requesting user (must own the session).

        Returns:
            Updated ResearchSessionResponse.

        Raises:
            ResearchNotFoundError: If not found or not owned by user.
        """
        session = await self.get_session(session_id, user_id)
        in_progress_statuses = {"pending", "planning", "researching", "verifying", "writing"}

        client = get_service_client()
        now = datetime.now(tz=UTC).isoformat()

        if session.status in in_progress_statuses:
            # Cancel the asyncio task if running
            task = _active_tasks.pop(str(session_id), None)
            if task and not task.done():
                task.cancel()

            await (
                client.table("research_sessions")
                .update({"status": "cancelled", "updated_at": now})
                .eq("id", str(session_id))
                .execute()
            )
            session_dict = session.model_dump()
            session_dict["status"] = "cancelled"
            return ResearchSessionResponse(**session_dict)
        else:
            # Soft delete
            await (
                client.table("research_sessions")
                .update({"deleted_at": now, "updated_at": now})
                .eq("id", str(session_id))
                .execute()
            )
            session_dict = session.model_dump()
            return ResearchSessionResponse(**session_dict)

    async def _update_session_status(
        self,
        session_id: UUID,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        """Internal helper to update session status in the database."""
        client = get_service_client()
        update_data: dict = {
            "status": status,
            "updated_at": datetime.now(tz=UTC).isoformat(),
        }
        if failure_reason:
            update_data["failure_reason"] = failure_reason

        await (
            client.table("research_sessions")
            .update(update_data)
            .eq("id", str(session_id))
            .execute()
        )

    @staticmethod
    def _row_to_response(row: dict) -> ResearchSessionResponse:
        """Convert a Supabase row dict to a ResearchSessionResponse."""
        return ResearchSessionResponse(
            id=UUID(row["id"]),
            question=row["research_question"],
            status=row["status"],
            config=row.get("config") or {},
            iteration_count=row.get("iteration_count") or 0,
            total_claims=row.get("total_claims"),
            verified_claims=row.get("verified_claims"),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            created_at=row["created_at"],
            failure_reason=row.get("failure_reason"),
        )
