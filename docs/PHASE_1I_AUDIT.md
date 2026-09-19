# Phase 1I: Reliability & Performance Hardening — Architecture & Systems Audit

**Date**: September 19, 2026  
**Status**: Completed Pre-Implementation Audit  
**Scope**: Production Reliability, LLM Fallback, EvidenceExtractor Performance Bottleneck, Transient Supabase Resilience, Observability (Langfuse), and Benchmark Reproducibility.

---

## 1. Current Architecture Relevant to Phase 1I

ResearchPilot AI executes deep research through a stateful LangGraph orchestration pipeline:
```text
FastAPI (/api/v1/research)
   ↓
ResearchService (enqueues background task, tracks lifecycle in Supabase)
   ↓
LangGraph ResearchState Graph:
   ├── 1. plan_research (PlannerAgent → sub-questions)
   ├── 2. web_research (WebResearchAgent via Tavily tool → parallel web searches)
   ├── 3. rank_sources (SourceRanker → URL deduplication & heuristic scoring)
   ├── 4. extract_evidence (EvidenceExtractor → parallel extraction bounded by semaphore)
   ├── 5. synthesize_claims (SynthesisAgent → extracts grounded factual claims)
   ├── 6. critic_verify (CriticAgent → verifies claims against source evidence)
   └── 7. write_report (WriterAgent → final markdown report with numbered citations)
   ↓
PersistenceService (Supabase PostgreSQL writes: sessions, plans, tasks, sources, evidence, claims, critic, reports, agent_runs)
```

The LLM abstraction layer consists of:
- `LLMRouter`: Manages structured generation via `generate_structured(messages, schema)`. It implements a provider hierarchy: **Gemini (Primary) → Groq (Secondary) → OpenRouter (Tertiary)**.
- `AsyncAgentRunCallbackHandler`: LangChain callback handler logging model names, token counts (`usage_metadata`), latency, and run statuses to the `agent_runs` table in Supabase.

---

## 2. Provider Configuration Audit

### Configured Models in `backend/app/core/config.py` vs Active Catalog:
| Provider | Configured Default / Env | Active Status / Findings | Resolution Required |
| :--- | :--- | :--- | :--- |
| **Google Gemini** | `gemini-flash-lite-latest` (resolves to `gemini-3.5-flash-lite`) | Active, supports structured output. However, constrained by free-tier cap of **500 Requests Per Day (RPD)** and **15 Requests Per Minute (RPM)**. | Keep model; add rate pacing and handle 429 quota exhaustion gracefully. |
| **Groq** | `llama-3.1-70b-versatile` | **DECOMMISSIONED**. Groq returns HTTP 400 Bad Request: `The model llama-3.1-70b-versatile has been decommissioned`. Active functional models with structured output: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`. | Update `GROQ_MODEL` default to verified active model (e.g. `openai/gpt-oss-20b` or `openai/gpt-oss-120b`). |
| **OpenRouter** | `mistralai/mixtral-8x7b-instruct` / `openai/gpt-4o-mini` | `mistralai/mixtral-8x7b-instruct` returns 404 (No endpoints). `openai/gpt-4o-mini` returns 402 (Insufficient credits). Active free models verified: `qwen/qwen3.8-27b:free`. | Update `OPENROUTER_MODEL` default to verified working model (e.g. `qwen/qwen3.8-27b:free`). |

---

## 3. Failure Causes Identified in Production Evaluation

In the 10-query benchmark (`evaluation/datasets/eval_10_queries.json`), 6 queries failed:

1. **Quota Exhaustion & Provider Failure Cascades (`eval-01`, `eval-07`, `eval-08`, `eval-09`, `eval-10`)**:
   - Because each research query currently executes 40–60 physical LLM calls, the Google AI Studio free-tier limit of 500 RPD was exhausted after ~8 queries.
   - When Gemini returned `429 RESOURCE_EXHAUSTED`, `LLMRouter` attempted fallback to Groq.
   - Groq returned `400 Bad Request (model_decommissioned)`. Because `_is_permanent_error` did not match "model_decommissioned", the router treated it as a transient error and retried 3 times with 15s/35s sleeps.
   - OpenRouter returned `402 Payment Required (insufficient credits)`.
   - Result: All providers failed, failing the entire graph run.
2. **Transient Supabase Connection Timeout (`eval-04`)**:
   - During session initialization in `ResearchService.create_session`, the initial `client.table("research_sessions").select(...)` encountered an HTTP `ConnectError` to Supabase.
   - Because no transient retry loop wrapped database operations, the API immediately returned HTTP 500 `INTERNAL_ERROR`.
3. **Execution Timeout During Report Generation (`eval-07`)**:
   - Gemini daily quota expired while the `WriterAgent` was attempting to write the report. The router performed repeated retries across all providers, accumulating 107 agent run records until the evaluation runner's 420-second timeout was reached.

---

## 4. EvidenceExtractor Bottleneck Analysis

### Call Flow & Inefficiencies:
- **Location**: `backend/app/graph/edges.py` (`route_to_extraction`), `backend/app/graph/nodes.py` (`extract_evidence`), `backend/app/agents/evidence_extractor.py`.
- **Current Flow**:
  1. `PlannerAgent` generates 4 sub-questions.
  2. `WebResearchAgent` retrieves 5 sources per sub-question (up to 20 raw sources).
  3. `SourceRanker` ranks and deduplicates sources by URL.
  4. `route_to_extraction` creates a separate LangGraph `Send` task for **every single (sub-question, source) pair**.
  5. 4 sub-questions × 4–5 sources = **16–20 individual LLM extraction calls**.
  6. Each call loads the full system prompt, JSON schema, and source text into a separate LLM roundtrip.
  7. Across 4 successful evaluation runs, `EvidenceExtractor` accounted for **174 out of 213 physical LLM calls (81.7%)**, consuming **~120–150 seconds (70% of total runtime)**.

### Optimizations Needed:
1. **Batching**: Group $N$ sources per sub-question (e.g. `EVIDENCE_BATCH_SIZE=2` or `3`) into a single structured extraction prompt with delimited source blocks.
2. **Concurrency Control**: Ensure `EVIDENCE_EXTRACTION_CONCURRENCY` is bounded (e.g., 2–4) with backoff pacing to prevent 429 burst collisions.
3. **Deduplication & Content Truncation**: Skip sources with empty or duplicate content; truncate raw sources to `RESEARCH_MAX_SOURCE_CONTENT_TOKENS` before LLM ingestion.
4. **Strict Traceability**: Domain `Evidence` entities must retain authoritative UUIDs and map strictly to the source ID in the batch.

---

## 5. Langfuse Integration Status

- **Status**: Non-functional (`401 Unauthorized` + No callback registered).
- **Audit Findings**:
  1. `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` configured in `.env` fail authentication (`Invalid credentials`) on both `https://cloud.langfuse.com` and `https://us.cloud.langfuse.com`.
  2. Neither `backend/app/llm/router.py`, `backend/app/graph/nodes.py`, nor `backend/app/services/research_service.py` ever imports or instantiates `langfuse.callback.CallbackHandler`.
- **Remediation**:
  - Implement a safe `get_langfuse_callback()` helper:
    - If `settings.langfuse_configured` is True, perform a lightweight non-blocking auth check.
    - If valid, return `CallbackHandler()`.
    - If invalid or unreachable, log a structured warning and return `None` without interrupting pipeline execution.
  - Attach the Langfuse handler (when active) to LangChain runnable configs alongside `AsyncAgentRunCallbackHandler`.
  - Add health diagnostic endpoint/unit test.

---

## 6. Proposed Minimal Changes

1. **LLM Provider Hardening (`app/llm/` & `app/core/config.py`)**:
   - Add lightweight provider preflight/health validation function (`validate_provider_health(provider_name)`).
   - Update `GROQ_MODEL` default to active model: `openai/gpt-oss-20b` (or `openai/gpt-oss-120b`).
   - Update `OPENROUTER_MODEL` default to active working model: `qwen/qwen3.8-27b:free`.
   - Update `LLMRouter._is_permanent_error`: include `decommissioned`, `model_decommissioned`, `unsupported model`, `resource_not_found`, `401`, `402`, `403`.
   - Add provider exhaustion tracking: if a provider experiences permanent failure or daily quota exhaustion, mark it inactive for the session/window to fail fast to the next provider.
   - Make retry sleep duration mockable or parameterized to avoid slowing unit tests.
2. **Evidence Extraction Batching & Performance Optimization (`app/agents/evidence_extractor.py`, `app/graph/edges.py`, `app/graph/nodes.py`)**:
   - Add `EVIDENCE_BATCH_SIZE: int = 2` (or 3) in `config.py`.
   - Update `route_to_extraction` to chunk `task_sources` into batches of `EVIDENCE_BATCH_SIZE`.
   - Implement `EvidenceExtractor.run_batch(sub_question, sources_batch)` with structured schema mapping extracted items to `source_id`.
   - Validate and reassign authoritative backend UUIDs to preserve 100% claim-to-evidence-to-source traceability.
3. **Database Transient Retry Wrapper (`app/core/database.py` & `app/services/persistence.py`)**:
   - Implement a lightweight `execute_with_retry` helper for Supabase queries encountering `httpx.ConnectError`, `ConnectTimeout`, or `ReadTimeout` (up to 3 attempts with exponential backoff and jitter).
   - Apply to session creation and critical persistence queries.
4. **Langfuse Telemetry Handler (`app/llm/observability.py`)**:
   - Create safe initialization module for Langfuse.
   - Inject into `nodes.py` callback lists when configured and healthy.

---

## 7. Files Expected to Change

- `backend/app/core/config.py`: Add `EVIDENCE_BATCH_SIZE`, update provider model defaults.
- `backend/app/llm/router.py`: Expand permanent error classification, fast-fail logic, health validation.
- `backend/app/llm/providers/groq.py`: Align default model and timeout settings.
- `backend/app/llm/providers/openrouter.py`: Align default model and timeout settings.
- `backend/app/agents/evidence_extractor.py`: Add batch extraction method with structured source attribution.
- `backend/app/graph/edges.py`: Batch source routing in `route_to_extraction`.
- `backend/app/graph/nodes.py`: Update `extract_evidence` node to handle source batches.
- `backend/app/core/database.py`: Add transient connection retry utility.
- `backend/app/services/persistence.py` & `research_service.py`: Utilize transient retry wrapper.
- `backend/app/llm/observability.py`: New safe Langfuse callback factory.
- `.env.example`: Update model identifiers and new batch configuration options.
- `evaluation/run_production_evaluation.py`: Support new Phase 1I metrics tracking and comparison output.

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **Evidence Misattribution in Batches** | LLM extracts snippet from Source B but tags Source A. | Distinct XML/bracket demarcations per source (`<source id="...">...<source>`), explicit schema field requiring `source_id`, and strict backend validation discarding items with unknown `source_id`. |
| **Prompt Size Growth** | Batching multiple sources could exceed prompt token limits. | Bound `EVIDENCE_BATCH_SIZE` to 2–3 sources; truncate individual source content to `RESEARCH_MAX_SOURCE_CONTENT_TOKENS` (2000 tokens). |
| **Provider Fallback Cascades** | Inappropriate fallback triggering on bad prompt syntax. | Preserve rule that Pydantic `ValidationError` fails fast and does not cascade across providers. |
| **Database Transaction Duplication** | Retrying inserts could cause duplicate key errors. | All persistence operations use deterministic UUIDs (`uuid5`) and upserts (`on_conflict="id"` or `on_conflict="session_id,url"`). |
| **Observability Overhead** | Langfuse network timeouts could stall research execution. | Langfuse is non-blocking with zero-timeout fallback; pipeline continues regardless of Langfuse availability. |
