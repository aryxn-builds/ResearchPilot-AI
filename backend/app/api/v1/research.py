"""Research API endpoints.

Implements all endpoints defined in API_SPEC.md for research sessions:

  POST   /api/v1/research                        — Submit research question
  GET    /api/v1/research                        — List research history
  GET    /api/v1/research/{research_id}          — Get session detail
  GET    /api/v1/research/{research_id}/status   — Lightweight status poll
  GET    /api/v1/research/{research_id}/stream   — SSE event stream
  GET    /api/v1/research/{research_id}/report   — Get completed report
  DELETE /api/v1/research/{research_id}          — Cancel or delete session

Route handlers contain NO business logic — all logic is in ResearchService.
AGENTS.md Rule A-01: API layer → Service layer boundary is strict.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import (
    CurrentUser,
    SSEUser,
    get_research_service,
)
from app.core.exceptions import ReportNotFoundError
from app.core.logging import get_logger
from app.schemas.common import (
    PaginatedResponse,
    SuccessResponse,
    make_paginated,
    make_success,
)
from app.schemas.research import (
    AsyncJobAccepted,
    DeleteResearchResponse,
    ReportResponse,
    ReportSummary,
    ResearchListItem,
    ResearchRequest,
    ResearchSessionResponse,
    ResearchStatus,
    ResearchStatusResponse,
)
from app.services.research_service import ResearchService, event_bus

logger = get_logger(__name__)
router = APIRouter()

# ─────────────────────────────────────────────
# POST /research — Submit a research question
# ─────────────────────────────────────────────


@router.post(
    "",
    status_code=202,
    summary="Submit a research question",
    description=(
        "Accepts a research question and optional configuration. "
        "Returns immediately with 202 Accepted while the research runs in the background. "
        "Use the returned stream_url to receive real-time progress events."
    ),
    response_model=SuccessResponse[AsyncJobAccepted],
)
async def submit_research(
    request: Request,
    body: ResearchRequest,
    user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    service: ResearchService = Depends(get_research_service),
) -> SuccessResponse[AsyncJobAccepted]:
    """Submit a new research question for processing."""
    session = await service.create_session(
        user_id=user.id,
        question=body.question,
        config=body.config,
        idempotency_key=idempotency_key,
    )

    # Bind user_id into rate limit state for middleware
    request.state.user_id = str(user.id)

    # Start background research task (asyncio — ADR-002)
    await service.start_research_task(session_id=session.id, user_id=user.id)

    base_url = str(request.base_url).rstrip("/")
    return make_success(
        AsyncJobAccepted(
            research_id=session.id,
            status=session.status,
            status_url=f"{base_url}/api/v1/research/{session.id}/status",
            stream_url=f"{base_url}/api/v1/research/{session.id}/stream",
        )
    )


# ─────────────────────────────────────────────
# GET /research — List research history
# ─────────────────────────────────────────────


@router.get(
    "",
    summary="List research history",
    description="Returns a paginated list of the authenticated user's research sessions.",
    response_model=PaginatedResponse[ResearchListItem],
)
async def list_research(
    user: CurrentUser,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=50, description="Results per page")] = 20,
    status: Annotated[ResearchStatus | None, Query(description="Filter by status")] = None,
    service: ResearchService = Depends(get_research_service),
) -> PaginatedResponse[ResearchListItem]:
    """List all research sessions for the authenticated user."""
    sessions, total = await service.list_sessions(
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
    )
    items = [
        ResearchListItem(
            id=s.id,
            question=s.question,
            status=s.status,
            verified_claims=s.verified_claims,
            total_claims=s.total_claims,
            created_at=s.created_at,
            completed_at=s.completed_at,
        )
        for s in sessions
    ]
    return make_paginated(data=items, page=page, page_size=page_size, total=total)


# ─────────────────────────────────────────────
# GET /research/{research_id} — Session detail
# ─────────────────────────────────────────────


@router.get(
    "/{research_id}",
    summary="Get research session detail",
    description="Returns full details for a specific research session owned by the authenticated user.",
    response_model=SuccessResponse[ResearchSessionResponse],
)
async def get_research(
    research_id: UUID,
    user: CurrentUser,
    service: ResearchService = Depends(get_research_service),
) -> SuccessResponse[ResearchSessionResponse]:
    """Get full detail for a research session."""
    session = await service.get_session(session_id=research_id, user_id=user.id)
    return make_success(session)


# ─────────────────────────────────────────────
# GET /research/{research_id}/status
# ─────────────────────────────────────────────


@router.get(
    "/{research_id}/status",
    summary="Get research status",
    description="Lightweight status poll for a research session. Use for polling when SSE is unavailable.",
    response_model=SuccessResponse[ResearchStatusResponse],
)
async def get_research_status(
    research_id: UUID,
    user: CurrentUser,
    service: ResearchService = Depends(get_research_service),
) -> SuccessResponse[ResearchStatusResponse]:
    """Lightweight status-only endpoint for polling."""
    session = await service.get_session(session_id=research_id, user_id=user.id)
    return make_success(
        ResearchStatusResponse(
            research_id=session.id,
            status=session.status,
            iteration_count=session.iteration_count,
        )
    )


# ─────────────────────────────────────────────
# GET /research/{research_id}/stream — SSE
# ─────────────────────────────────────────────


@router.get(
    "/{research_id}/stream",
    summary="Stream research progress events",
    description=(
        "Server-Sent Events stream for real-time research progress. "
        "Authenticate via ?token=<jwt> query parameter. "
        "Events follow the schema defined in API_SPEC.md."
    ),
    response_class=StreamingResponse,
    # SSE uses query-param auth — not Bearer, so no CurrentUser dependency here
)
async def stream_research(
    research_id: UUID,
    user: SSEUser,
    service: ResearchService = Depends(get_research_service),
) -> StreamingResponse:
    """Open a Server-Sent Events stream for research progress.

    Phase 1A: Emits a heartbeat every 15 seconds and closes when the
    session reaches a terminal state. LangGraph events will be injected
    in Phase 1B when the graph is implemented.
    """
    # Verify session ownership
    session = await service.get_session(session_id=research_id, user_id=user.id)

    async def _event_generator() -> AsyncIterator[str]:
        """Yield SSE-formatted events until the session completes."""
        terminal_states = {"completed", "failed", "cancelled"}

        q = event_bus.subscribe(str(research_id))
        try:
            # Re-fetch session status AFTER subscribing to avoid missing terminal events
            session = await service.get_session(session_id=research_id, user_id=user.id)

            # Send initial status event
            yield _sse_event(
                event="status_update",
                data={"research_id": str(research_id), "status": session.status},
            )

            # If already in terminal state, close immediately
            if session.status in terminal_states:
                yield _sse_event(
                    event="done", data={"research_id": str(research_id), "status": session.status}
                )
                return

            while True:
                try:
                    event_type, data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield _sse_event(event=event_type, data=data)

                    if event_type in ("done", "error"):
                        break
                except TimeoutError:
                    # Heartbeat
                    yield _sse_event(event="heartbeat", data={})
        finally:
            event_bus.unsubscribe(str(research_id), q)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event string.

    Args:
        event: The event type name.
        data: The event payload (will be JSON-encoded).

    Returns:
        A properly formatted SSE string ending with double newline.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────
# GET /research/{research_id}/report
# ─────────────────────────────────────────────


@router.get(
    "/{research_id}/report",
    summary="Get research report",
    description="Returns the completed research report. Only available when status is 'completed'.",
    response_model=SuccessResponse[ReportResponse],
)
async def get_report(
    research_id: UUID,
    user: CurrentUser,
    format: Annotated[
        str, Query(description="Response format. Currently only 'json' is supported.")
    ] = "json",
    service: ResearchService = Depends(get_research_service),
) -> SuccessResponse[ReportResponse]:
    """Retrieve the completed research report.

    Phase 1A: Returns ReportNotFoundError until the WriterAgent is implemented (Phase 1B).
    """
    # Verify session ownership first
    session = await service.get_session(session_id=research_id, user_id=user.id)

    if session.status != "completed":
        raise ReportNotFoundError(str(research_id))

    # Fetch report from DB
    from app.core.database import get_service_client

    client = get_service_client()
    result = await client.table("reports").select("*").eq("session_id", str(research_id)).execute()

    if not result.data:
        raise ReportNotFoundError(str(research_id))

    row = result.data[0]
    db_citation_map = row.get("citation_map", {})
    source_ids = list(db_citation_map.values())
    
    sources_map = {}
    if source_ids:
        # Fetch sources to resolve url and title
        sources_res = await client.table("sources").select("id, url, title").in_("id", source_ids).execute()
        for src in sources_res.data or []:
            sources_map[src["id"]] = src
            
    citation_map_api = {}
    for marker, src_id in db_citation_map.items():
        src_data = sources_map.get(src_id, {})
        citation_map_api[marker] = {
            "source_id": src_id,
            "url": src_data.get("url", ""),
            "title": src_data.get("title")
        }

    return make_success(
        ReportResponse(
            research_id=research_id,
            generated_at=row.get("generated_at") or row["created_at"],
            content_markdown=row["content_markdown"],
            citation_map=citation_map_api,
            total_citations=row.get("total_citations", 0),
            word_count=row.get("word_count"),
            section_count=row.get("section_count"),
            summary=ReportSummary(
                total_claims=session.total_claims or 0,
                verified_claims=session.verified_claims or 0,
                excluded_claims=(session.total_claims or 0) - (session.verified_claims or 0),
                iterations=session.iteration_count or 0,
            ),
        )
    )


# ─────────────────────────────────────────────
# DELETE /research/{research_id}
# ─────────────────────────────────────────────


@router.delete(
    "/{research_id}",
    summary="Cancel or delete a research session",
    description=(
        "Cancels an in-progress session or soft-deletes a completed one. "
        "In-progress sessions stop immediately; completed sessions are hidden from history."
    ),
    response_model=SuccessResponse[DeleteResearchResponse],
)
async def delete_research(
    research_id: UUID,
    user: CurrentUser,
    service: ResearchService = Depends(get_research_service),
) -> SuccessResponse[DeleteResearchResponse]:
    """Cancel or soft-delete a research session."""
    updated = await service.cancel_or_delete_session(session_id=research_id, user_id=user.id)
    return make_success(DeleteResearchResponse(research_id=updated.id, status=updated.status))
