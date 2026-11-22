"""Phase 1J correctness checks with local provider and persistence doubles."""

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.agents.evidence_extractor import ExtractionResult, LLMEvidenceItem
from app.agents.synthesis import SynthesisResult
from app.core import research_mode
from app.graph import nodes
from app.graph.research_graph import research_graph
from app.llm.router import LLMRouter
from app.schemas.agent import Claim, CriticResult, Report, ResearchPlan, SubQuestion
from app.schemas.research import ResearchConfig, ResearchSessionResponse
from app.services import research_service

DATASET = Path(__file__).resolve().parents[3] / "evaluation/datasets/eval_10_queries.json"


@pytest.mark.parametrize(("question", "mode", "expected"), [
    ("What is RAG?", "auto", "fast"),
    ("Compare LangChain and LangGraph.", "auto", "fast"),
    ("Analyze AI impacts across India and the EU.", "auto", "deep"),
    ("Explain AI.", "auto", "deep"),
    ("What is RAG?", "deep", "deep"),
    ("Analyze AI impacts across India and the EU.", "fast", "fast"),
])
def test_mode(question: str, mode: str, expected: str) -> None:
    assert ResearchConfig().mode == "deep"
    assert research_mode.resolve_mode(question, mode) == expected


@pytest.mark.parametrize("mode", ["fast", "deep"])
async def test_dataset_graph(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the original dataset through the real graph with controlled IO."""
    calls: list[str] = []
    durations: list[float] = []
    call_counts: list[int] = []
    verified = 0
    topics = ["apple", "cobalt", "orbit", "hydrogen", "tundra", "guitar", "bronze", "ruby"]
    writes = AsyncMock()
    monkeypatch.setattr(nodes, "persistence_service", writes)
    monkeypatch.setattr(nodes, "_get_callbacks", lambda *_: [])
    monkeypatch.setattr(nodes, "_evidence_extraction_semaphore", None)

    async def search(**kwargs: object) -> dict:
        results = [{"url": f"https://{topic}.example/doc", "title": topic,
                    "content": f"The experiment reported {topic} observations in laboratory conditions."}
                   for topic in topics[:int(str(kwargs["max_results"]))]]
        results.append({**results[0], "url": results[0]["url"] + "?utm_source=test"})
        results.append({**results[0], "url": "https://mirror.example/doc"})
        return {"results": results}

    async def generate(messages: list, schema: type[BaseModel], **_kwargs: object) -> BaseModel:
        calls.append(schema.__name__)
        content = messages[-1].content
        if schema is ResearchPlan:
            return ResearchPlan(sub_questions=[
                SubQuestion(id=str(uuid4()), question="Compare the results?", research_type="web"),
            ])
        if schema is ExtractionResult:
            sources = re.findall(r'<source id="([^"]+)"[^>]*>\s*<raw_source>\s*([^\n]+)', content)
            return ExtractionResult(evidence_items=[
                *(LLMEvidenceItem(source_id=sid, snippet=quote) for sid, quote in sources),
                LLMEvidenceItem(source_id=str(uuid4()), snippet="Unsupported attribution"),
                LLMEvidenceItem(source_id=sources[0][0], snippet="Invented quote"),
            ])
        if schema is SynthesisResult:
            rows = json.loads(content.split("<raw_source>\n")[1].split("\n</raw_source>")[0])
            return SynthesisResult(claims=[
                Claim(id=str(uuid4()), statement=rows[0]["snippet"], evidence_ids=[rows[0]["id"]]),
                Claim(id=str(uuid4()), statement="Unsupported assertion", evidence_ids=[str(uuid4())]),
                Claim(id=str(uuid4()), statement="Separate unverified assertion", evidence_ids=[rows[0]["id"]]),
            ] if mode == "fast" else [
                Claim(id=str(uuid4()), statement=rows[0]["snippet"], evidence_ids=[rows[0]["id"]]),
            ])
        if schema is CriticResult:
            rows = json.loads(content.split("Claims to Verify:\n")[1])
            return CriticResult(claims=[
                Claim(**row, verification_status="verified")
                for row in rows if row["statement"].startswith("The experiment")
            ])
        if schema is Report:
            return Report(markdown="## Findings\n\nThe experiment reported observations [1].",
                          total_citations=1, word_count=6, section_count=1)
        raise AssertionError(schema)

    monkeypatch.setattr(nodes.tavily_tool.client, "search", search)
    monkeypatch.setattr(nodes.llm_router, "generate_structured", generate)
    token = research_mode.fast_research.set(mode == "fast")
    try:
        for item in json.loads(DATASET.read_text(encoding="utf-8")):
            calls.clear()
            start = perf_counter()
            final = await research_graph.ainvoke({"session_id": str(uuid4()), "research_question": item["query"]})
            durations.append(perf_counter() - start)
            call_counts.append(len(calls))
            report = final["report"]
            assert report.citation_map
            assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", report.markdown)
            assert {c.source_id for c in report.citation_map} <= {s.id for s in final["sources"]}
            assert all(e.source_id in {s.id for s in final["sources"]} for e in final["evidence_items"])
            verified += sum(c.verification_status == "verified" for c in final["critic_result"].claims)
            if mode == "fast":
                assert len(final["research_plan"].sub_questions) == 1
                assert len(final["sources"]) <= 6
                assert all("mirror" not in s.url and "utm_" not in s.url for s in final["sources"])
                assert all(e.snippet.startswith("The experiment") for e in final["evidence_items"])
                assert "Unsupported" not in report.markdown and "unverified assertion" not in report.markdown
                assert calls.count("ExtractionResult") <= 2
                assert "ResearchPlan" not in calls and "Report" not in calls
            else:
                assert "ResearchPlan" in calls and "Report" in calls
            assert calls.count("CriticResult") == 1
        assert writes.save_evidence.await_count == len(durations)
    finally:
        research_mode.fast_research.reset(token)
    ordered = sorted(durations)
    print(f"{mode}: {len(ordered)}/10, median={(ordered[4]+ordered[5])/2:.4f}s, "
          f"p90={ordered[8]:.4f}s, invocation counts={call_counts}, verified={verified}")


async def test_router_skips_daily_quota_and_bounds_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class Output(BaseModel):
        state: str

    router = LLMRouter()
    gemini, groq, openrouter = MagicMock(), MagicMock(), MagicMock()
    for provider in (gemini, groq, openrouter):
        provider.model_copy.return_value = provider
    gemini.with_structured_output.return_value.ainvoke = AsyncMock(
        side_effect=Exception("429 rate_limit_exceeded, tokens per day (TPD) exhausted"),
    )

    async def slow(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(1)

    groq.with_structured_output.return_value.ainvoke = AsyncMock(side_effect=slow)
    openrouter.with_structured_output.return_value.ainvoke = AsyncMock(return_value={"state": "ok"})
    router.gemini, router.groq, router.openrouter = gemini, groq, openrouter
    monkeypatch.setattr(nodes.settings, "PRIMARY_LLM_PROVIDER", "gemini")
    monkeypatch.setattr(nodes.settings, "FAST_LLM_TIMEOUT_SECONDS", 0.01)
    token = research_mode.fast_research.set(True)
    try:
        for _ in range(2):
            assert (await router.generate_structured("prompt", Output)).state == "ok"
    finally:
        research_mode.fast_research.reset(token)
    gemini.with_structured_output.return_value.ainvoke.assert_awaited_once()
    groq.with_structured_output.return_value.ainvoke.assert_awaited_once()
    assert openrouter.with_structured_output.return_value.ainvoke.await_count == 2


@pytest.mark.parametrize("scenario", ["deadline", "missing_report", "failed_write"])
async def test_no_completion_for_incomplete_work(monkeypatch: pytest.MonkeyPatch, scenario: str) -> None:
    service = research_service.ResearchService()
    sid = uuid4()
    session = ResearchSessionResponse(id=sid, question="What is RAG?", status="pending",
                                      config={"mode": "fast"}, created_at=datetime.now(UTC))
    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    status = AsyncMock()
    publish = AsyncMock()
    db = MagicMock()
    monkeypatch.setattr(service, "_update_session_status", status)
    monkeypatch.setattr(research_service.event_bus, "publish", publish)
    monkeypatch.setattr(research_service, "get_service_client", lambda: db)
    monkeypatch.setattr(nodes.settings, "FAST_RESEARCH_TIMEOUT_SECONDS", 0.01 if scenario == "deadline" else 1)

    async def stream(state: dict, **_kwargs: object):
        if scenario == "deadline":
            await asyncio.sleep(1)
        if scenario == "failed_write":
            state["report"] = Report(markdown="A finding", total_citations=0, word_count=2, section_count=1)
        yield "values", state

    monkeypatch.setattr(research_service.research_graph, "astream", stream)
    if scenario == "failed_write":
        monkeypatch.setattr(research_service, "execute_with_retry", AsyncMock(side_effect=ValueError))
    await service._run_research_graph(sid, uuid4())
    assert status.await_args.args[1] == "failed"
    assert publish.await_args.args[1] == "done"
    assert publish.await_args.args[2]["status"] == "failed"
    if scenario == "deadline":
        assert "time limit" in publish.await_args.args[2]["failure_reason"]
    assert not research_mode.fast_research.get()

async def test_completion_after_report_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    service = research_service.ResearchService()
    sid, owner = uuid4(), uuid4()
    session = ResearchSessionResponse(
        id=sid, question="What is RAG?", status="pending",
        config={"mode": "fast"}, created_at=datetime.now(UTC),
    )
    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=session))
    status = AsyncMock()
    monkeypatch.setattr(service, "_update_session_status", status)
    db = MagicMock()
    db.table.side_effect = lambda name: tables[name]
    tables = {"reports": MagicMock(), "research_sessions": MagicMock()}
    tables["reports"].upsert.return_value.execute = AsyncMock()
    tables["research_sessions"].update.return_value.eq.return_value.execute = AsyncMock()
    monkeypatch.setattr(research_service, "get_service_client", lambda: db)

    async def stream(state: dict, **_kwargs: object):
        assert research_mode.fast_research.get()
        for node in ("plan_research", "synthesize_claims", "synthesize_claims", "critic_verify"):
            yield "updates", {node: {}}
        state["report"] = Report(markdown="## Findings", total_citations=0, word_count=1, section_count=1)
        yield "values", state

    graph_stream = MagicMock(side_effect=stream)
    monkeypatch.setattr(research_service.research_graph, "astream", graph_stream)
    published = research_service.event_bus.subscribe(str(sid))
    try:
        await service._run_research_graph(sid, owner)
        events = [published.get_nowait() for _ in range(published.qsize())]
    finally:
        research_service.event_bus.unsubscribe(str(sid), published)
    graph_stream.assert_called_once()
    report = tables["reports"].upsert.call_args
    assert report.args[0]["user_id"] == str(owner)
    assert report.kwargs == {"on_conflict": "session_id"}
    tables["reports"].upsert.return_value.execute.assert_awaited_once()
    assert tables["research_sessions"].update.call_args.args[0]["status"] == "completed"
    assert [body["status"] for _, body in events] == [
        "planning", "researching", "verifying", "writing", "completed",
    ]
    assert events[-1][0] == "done"
