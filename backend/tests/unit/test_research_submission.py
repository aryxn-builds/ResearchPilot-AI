from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from postgrest import AsyncPostgrestClient
from supabase_auth.errors import AuthApiError

from app.api import deps
from app.services import research_service
from app.services.research_service import ResearchService


@pytest.mark.parametrize("mode", ["fast", "deep"])
@pytest.mark.parametrize("lose_insert_response", [False, True])
async def test_concurrent_submission_and_replay(
    async_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    lose_insert_response: bool,
) -> None:
    """Same authenticated payload and key admit one row and one graph run."""
    owner = str(uuid4())
    rows: dict[str, dict] = {}
    request_count = 0

    async def postgrest(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        assert request.url.params.get("user_id") == f"eq.{owner}" or request.method == "POST"
        assert "idempotency_key" not in request.url.params
        if request.method == "GET":
            row_id = request.url.params.get("id", "").removeprefix("eq.")
            if not row_id:
                await asyncio.sleep(0)
                return httpx.Response(200, headers={"content-range": "*/0"}, json=[])
            return httpx.Response(200, json=[rows[row_id]] if row_id in rows else [])
        payload = json.loads(request.content)
        if request.method == "POST":
            request_count += 1
            assert "resolution=ignore-duplicates" in request.headers["prefer"]
            assert request.url.params["on_conflict"] == "id"
            assert "idempotency_key" not in payload
            session_id = payload["id"]
            if session_id in rows:
                return httpx.Response(201, json=[])
            rows[session_id] = payload
            if lose_insert_response:
                raise httpx.RemoteProtocolError("Connection closed after commit")
            return httpx.Response(201, json=[payload])
        assert request.method == "PATCH"
        assert request.url.params["status"] == "eq.pending"
        row = rows[request.url.params["id"].removeprefix("eq.")]
        if row["status"] != "pending":
            return httpx.Response(200, json=[])
        row.update(payload)
        return httpx.Response(200, json=[row])

    auth = AsyncMock(return_value=SimpleNamespace(
        user=SimpleNamespace(id=owner, email="test@example.com", role="authenticated"),
    ))
    graph = AsyncMock()
    monkeypatch.setattr(deps, "get_anon_client", lambda: SimpleNamespace(
        auth=SimpleNamespace(get_user=auth),
    ))
    monkeypatch.setattr(ResearchService, "_run_research_graph", graph)
    async with httpx.AsyncClient(transport=httpx.MockTransport(postgrest)) as database_http:
        database = AsyncPostgrestClient("https://db.example", http_client=database_http)
        monkeypatch.setattr(research_service, "get_service_client", lambda: database)
        headers = {"Authorization": "Bearer test-token", "Idempotency-Key": str(uuid4())}
        body = {"question": "what is GPT?", "config": {"mode": mode}}

        first, second = await asyncio.gather(*(
            async_client.post("/api/v1/research", headers=headers, json=body) for _ in range(2)
        ))
        auth.assert_any_await("test-token")
        assert first.status_code == second.status_code == 202
        session_id = first.json()["data"]["research_id"]
        assert second.json()["data"]["research_id"] == session_id
        assert list(rows) == [session_id]
        assert rows[session_id]["config"]["mode"] == mode
        graph.assert_awaited_once()

        rows[session_id]["status"] = "completed"
        replay = await async_client.post("/api/v1/research", headers=headers, json=body)
        assert replay.json()["data"]["status"] == "completed"
        assert replay.json()["data"]["research_id"] == session_id
        graph.assert_awaited_once()
        conflict = await async_client.post(
            "/api/v1/research", headers=headers, json={**body, "question": "A different question?"}
        )
        assert conflict.status_code == 409
        assert 1 <= request_count <= (3 if lose_insert_response else 2)


async def test_submission_errors(
    async_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expired JWT, validation, and database outages have distinct statuses."""
    auth = AsyncMock(side_effect=AuthApiError("JWT expired", 401, "bad_jwt"))
    monkeypatch.setattr(deps, "get_anon_client", lambda: SimpleNamespace(
        auth=SimpleNamespace(get_user=auth),
    ))
    create = AsyncMock(side_effect=httpx.ReadTimeout("database timed out"))
    monkeypatch.setattr(ResearchService, "create_session", create)
    headers = {"Authorization": "Bearer test-token", "Idempotency-Key": str(uuid4())}
    body = {"question": "what is GPT?", "config": {"mode": "fast"}}

    expired = await async_client.post("/api/v1/research", headers=headers, json=body)
    assert expired.status_code == 401
    create.assert_not_awaited()

    auth.side_effect = AuthApiError("Auth unavailable", 503, "unexpected_failure")
    monkeypatch.setattr(deps, "asyncio", SimpleNamespace(sleep=AsyncMock()))
    auth_unavailable = await async_client.post("/api/v1/research", headers=headers, json=body)
    assert auth_unavailable.status_code == 503
    assert auth_unavailable.json()["error"]["code"] == "AUTH_UNAVAILABLE"
    create.assert_not_awaited()

    auth.side_effect = None
    auth.return_value = SimpleNamespace(user=SimpleNamespace(
        id=str(uuid4()), email="test@example.com", role="authenticated",
    ))
    invalid = await async_client.post(
        "/api/v1/research", headers=headers, json={**body, "config": {"mode": "invalid"}}
    )
    assert invalid.status_code == 422
    create.assert_not_awaited()

    unavailable = await async_client.post("/api/v1/research", headers=headers, json=body)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
