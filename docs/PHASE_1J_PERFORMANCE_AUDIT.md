# Phase 1J performance audit

The pre-change production archive records 4 completions in 10 attempts. Completed-run median was 208.61 s (range 153.45–213.02 s), with 213 recorded model invocations, 30 recorded fallbacks and 458,361 reported tokens across those four completions. The archive estimates $0.043506 using its historical pricing assumptions. It does not reliably count SDK-internal retries, failed-run usage or current prices.

A fresh read-only Supabase probe succeeded (HTTP 200 in 0.696 s). That measurement covers one read from this workstation and cannot stand in for write latency or report latency. The automated approval review rejected a fresh ten-query run using the legacy hardcoded QA login because it would consume live quotas and write to production. No live research requests were submitted by that attempt.

| Area | Pre-change finding |
| --- | --- |
| Graph and SSE | One `astream` call emits both updates and cumulative values. Search and evidence fan out within their respective stages. Stages are dependent and sequential. Extraction emits one update per batch, causing repeated writing of the same verifying status. |
| Planner/search | Planner calls the LLM for every question. Tavily requests raw content per task. Ranking deduplicates exact URLs only and assigns constant relevance. |
| Evidence | Task-aware batches already exist. Extraction holds the semaphore for an extra 0.5 s after each call. Single-source extraction can silently reattribute unknown IDs. |
| Synthesis and Critic | Revising claims reruns synthesis and rewrites the same evidence. Critic persistence updates each claim individually. |
| Writer | A separate structured call expands the report after verification. The sanitizer resolves markers against the source list. |
| Router | Up to three router attempts per provider on top of SDK retries. Backoff may wait up to 15 s per retry. Daily depletion can disable a provider for the process lifetime. |
| Database | Plan/tasks, sources, evidence, claim/evidence links, critic results, report and terminal status have dependency ordering. Model attempt telemetry also writes on the invocation path. |
| Timeout | The configured session deadline was not applied to graph execution. The service could mark a session completed when the graph yielded no report. |

The archive provides historical invocation durations and token counts in `agent_runs`; those are not exact stage wall times when nodes overlap or include persistence. Exact pre-change stage, DB write, and rate-limit wait latencies were unavailable. The optimized path adds stage/attempt timing and records persistence times separately. Refer to the comparison report for measured conditions.
