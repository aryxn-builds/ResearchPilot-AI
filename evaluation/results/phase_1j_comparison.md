# Phase 1J performance comparison

## Historical live results and new local results

| Metric | Historical live baseline | Phase 1J Fast with mocks | Phase 1J Deep with mocks |
| --- | ---: | ---: | ---: |
| Completed / attempted | 4 / 10 | 10 / 10 | 10 / 10 |
| Failure rate | 60% | 0% | 0% |
| Completed-run median | 208.61 s | 0.0082 s | 1.0247 s |
| Completed-run P90 (nearest rank) | 213.02 s | 0.0092 s | 1.0312 s |
| Model invocations per completion | 53.25 mean recorded | 4 simulated | 6 simulated |
| Evidence extraction invocations per completion | No comparable archive count | 2 simulated | 2 simulated |
| Recorded fallback attempts | 30 across 4 completions | None in dataset fixture | None in dataset fixture |
| Tokens per successful query | 114,590.25 mean reported | Unmeasured | Unmeasured |
| Estimated cost per successful query | $0.010877 using historical rates | Unmeasured | Unmeasured |
| Reports with citation failures | 0 / 4 | 0 / 10 fixtures | 0 / 10 fixtures |
| Overall claim verification rate | 70 / 72 | Synthetic decisions | Synthetic decisions |

The historical P90 is the maximum under nearest-rank with four completions.
Historical results come from [baseline_summary.json](baseline_summary.json).
The separate 262.9 s completed run was reported outside this dataset summary.

Both local columns execute the real LangGraph with the unchanged
[10-query dataset](../datasets/eval_10_queries.json) and deterministic Tavily,
LLM and persistence doubles. They measure graph time on one workstation.
Deep's configured extraction wait contributes roughly one second across its
two serialized batches in this fixture. Neither mock column measures external
provider performance, production success rate, report usefulness, or live
database write overhead. The simulated call counts are specific to the sources
and outcomes in the fixture.

## Live rerun

The user-requested live comparison remains unmeasured. The automatic approval
review blocked a fresh run using the old runner's hardcoded QA login because the
run would consume live provider quota and persist production data. No benchmark
research was submitted using that login.

Use a provisioned QA account and an isolated QA Supabase project with a deployment
pointing to that same project. Set `EVAL_QA_EMAIL`, `EVAL_QA_PASSWORD` and
`EVAL_API_BASE` in the runner environment. Run one dataset at a time, using
the same configured providers, search depth, concurrency and working quotas.
Use the same dataset and runner with the original backend revision for a new Deep
baseline. Record exact revisions, region, cold starts and provider model IDs.

```sh
cd backend
uv run python ../evaluation/run_production_evaluation.py --mode deep --output-dir scratch/phase1j
uv run python ../evaluation/run_production_evaluation.py --mode fast --output-dir scratch/phase1j
```

The runner requires fresh output directories and records failed attempts in the
success denominator. Completed-run latency includes the status polling interval.
Its historical cost formula is an estimate and must be recalibrated for the
configured models before making billing claims. Reconcile the reports with
`research_stage`, `research_evidence_queue`, `research_llm_attempt`,
`llm_retry_backoff`, `research_db_write` and
`research_completion_persistence` logs using the session ID. Compare stage wall
time across fan-out rather than summing overlapping worker durations. Include
failed sessions when collecting provider attempts and quota exhaustion events.
The database agent-run records supply tokens where the provider reports usage.
