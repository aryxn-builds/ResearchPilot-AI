import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from supabase_auth.errors import AuthApiError

from app.api import deps
from app.core.exceptions import ResearchNotFoundError
from app.schemas.research import ResearchSessionResponse
from app.services.research_service import event_bus


async def test_research_progress_endpoints_require_bearer_and_ownership(
    async_client: httpx.AsyncClient, app_with_mocked_db: FastAPI, monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, other, session_id = uuid4(), uuid4(), uuid4()

    async def get_user(token: str) -> SimpleNamespace:
        if token == "expired":
            raise AuthApiError("JWT expired", 401, "bad_jwt")
        return SimpleNamespace(user=SimpleNamespace(
            id=str(owner if token == "owner" else other), email="", role="authenticated",
        ))

    async def get_session(session_id: UUID, user_id: UUID) -> ResearchSessionResponse:
        if user_id != owner:
            raise ResearchNotFoundError(str(session_id))
        return ResearchSessionResponse(
            id=session_id, question="what is GPT?", status="completed",
            created_at=datetime.now(UTC),
        )

    lookup = AsyncMock(side_effect=get_session)
    monkeypatch.setattr(deps, "get_anon_client", lambda: SimpleNamespace(
        auth=SimpleNamespace(get_user=get_user),
    ))
    app_with_mocked_db.dependency_overrides[deps.get_research_service] = lambda: (
        SimpleNamespace(get_session=lookup)
    )
    base = f"/api/v1/research/{session_id}"
    for path in (base, f"{base}/status", f"{base}/stream"):
        assert (await async_client.get(path, headers={"Authorization": "Bearer other"})).status_code == 404
        assert (await async_client.get(path, headers={"Authorization": "Bearer expired"})).status_code == 401
    assert (await async_client.get(f"{base}/stream?token=owner")).status_code == 401

    headers = {"Authorization": "Bearer owner"}
    detail = await async_client.get(base, headers=headers)
    assert detail.json()["data"]["question"] == "what is GPT?"
    status = await async_client.get(f"{base}/status", headers=headers)
    assert status.json()["data"]["research_id"] == str(session_id)
    stream = await async_client.get(f"{base}/stream", headers=headers)
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "event: status_update" in stream.text
    assert "event: done" in stream.text
    assert '"status": "completed"' in stream.text

    async def complete_during_connect(session_id: UUID, user_id: UUID) -> ResearchSessionResponse:
        assert user_id == owner
        if lookup.await_count == 2:
            await event_bus.publish(str(session_id), "done", {"status": "completed"})
        return ResearchSessionResponse(
            id=session_id, question="what is GPT?", status="researching",
            created_at=datetime.now(UTC),
        )

    lookup.reset_mock()
    lookup.side_effect = complete_during_connect
    raced = await asyncio.wait_for(async_client.get(f"{base}/stream", headers=headers), timeout=3)
    assert '"status": "researching"' in raced.text
    assert '"status": "completed"' in raced.text
