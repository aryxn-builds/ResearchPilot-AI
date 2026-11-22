# Phase 1J final report

**PARTIAL.** Fast Research is implemented. Local checks cover both modes and the
original evaluation dataset. The 50-second completed-query median and 90% live
success targets still require measurements using healthy live providers.

## Implementation

- The Research form defaults to **Deep Research**. Users can select **Fast
  Research**. API callers can also send `config.mode=auto` for conservative,
  deterministic routing. The resolved mode is stored in the session config.
- Fast uses one direct Tavily task, retains up to six ranked sources by default,
  and removes tracking URL variants and near-duplicate text. Tavily's query
  excerpts supply bounded context. Evidence batches carry exact source IDs and
  discard unknown IDs and snippets absent from the supplied source.
- Fast calls synthesis followed by an independent Critic. Unverified and
  contradicted claims are excluded. The Writer renders whole verified claims
  with server-generated references and fails if no cited finding remains.
  Deep uses its existing planner, verification loop and report writer.
- The router bounds attempts and applies timeouts, validates structured
  output, and skips providers during quota or transient-error cooldowns.
  Daily quota exhaustion cools down for up to 24 hours from detection.
  Provider model IDs remain configurable. Routing uses configured priority.
- The service streams one graph execution, emits each phase transition once,
  and only emits completion after report persistence. Fast core writes fail
  the session when unsuccessful. Claim status updates are grouped and completed
  evidence is saved once. The active page shows stage events, mode, elapsed
  duration, and the final report or failure state.

## Timing budgets

| Stage | Target | Live Phase 1J timing |
| --- | ---: | --- |
| Planning | 3 s | Unmeasured |
| Web research and ranking | 10 s | Unmeasured |
| Evidence extraction | 14 s | Unmeasured |
| Synthesis and verification | 12 s | Unmeasured |
| Report creation and persistence | 11 s | Unmeasured |
| End to end | 50 s | Unmeasured |

The default Fast execution deadline is 65 seconds and the per-provider attempt
budget is 12 seconds. A timeout fails the session with an explicit reason.
See [comparison results](../evaluation/results/phase_1j_comparison.md) for the
test conditions and [performance audit](PHASE_1J_PERFORMANCE_AUDIT.md) for the
historical baseline and pre-change findings.

## Recommended starting configuration

Use the Fast defaults in [the environment example](../.env.example).
Keep one extraction slot on constrained provider quotas. Tune the retained-source
cap, batch size, output budget, and concurrency with real QA data. Keep Deep
for broad questions whose coverage cannot fit a short report. Critic decisions
are model judgments, so a real report review is needed to assess semantic
verification quality and whether Tavily snippets provide enough coverage.

## Changed files

| Area | Files |
| --- | --- |
| Settings and mode | `.env.example`, `backend/app/core/config.py`, `backend/app/core/research_mode.py`, `backend/app/schemas/research.py` |
| Graph and agents | `backend/app/graph/edges.py`, `nodes.py`, `research_graph.py`, `backend/app/agents/critic.py`, `evidence_extractor.py`, `synthesis.py`, `web_research.py`, `writer.py` |
| Search and providers | `backend/app/tools/tavily.py`, `backend/app/llm/router.py`, `backend/app/llm/providers/gemini.py`, `groq.py`, `openrouter.py` |
| API and persistence | `backend/app/api/v1/research.py`, `backend/app/services/research_service.py`, `persistence.py` |
| Frontend | `frontend/src/app/(dashboard)/research/new/page.tsx`, `frontend/src/app/(dashboard)/research/active/[id]/page.tsx` |
| Tests and evaluation | `backend/tests/unit/test_phase1j.py`, `evaluation/run_production_evaluation.py`, `evaluation/results/phase_1j_comparison.md` |
| Documentation | `docs/API_SPEC.md`, `docs/PHASE_1J_PERFORMANCE_AUDIT.md`, `docs/PHASE_1J_FINAL_REPORT.md` |

## Validation and remaining risks

The frontend passed TypeScript, ESLint and the Next.js production build. The
backend suite exercises authorization, SSE, persistence, legacy Deep behavior,
mode routing, quote attribution, timeouts and provider cooldowns. The new dataset
tests validate citations with deterministic fixtures. Production provider
availability, report completeness, latency, token usage and cost remain
unverified. Running the live comparison requires a designated QA environment
and authorization for its provider quotas and database writes.
