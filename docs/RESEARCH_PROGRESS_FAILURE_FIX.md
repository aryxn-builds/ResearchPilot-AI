# Research progress recovery fix

**Verdict: PARTIAL.** The deployed authentication mismatch was reproduced. Production verification after rollout requires an authenticated QA session.

The FastAPI detail, status, and stream endpoints now use the same bearer dependency, which validates the token through Supabase Auth. The stream still checks session ownership before returning events. RLS policies and Supabase migrations are unchanged.

The active page loads the owner-scoped session detail as its source for the question, mode, current stage, and failure reason. It opens an authenticated fetch stream while the job is active and keeps checking persisted status when the stream closes or misses events. A persisted completed status opens the report. Refresh and reconnect use read-only requests and never submit or restart a job.

The UI separates authorization errors, missing sessions, invalid IDs or states, service failures, and temporary stream interruptions. It shows the real question and deduplicated stage messages received from the backend. An empty activity panel is no longer shown.

## Changed files

- Backend authentication and streaming in `backend/app/api/deps.py` and `backend/app/api/v1/research.py`.
- Active research page and recovery in `frontend/src/app/(dashboard)/research/active/[id]/page.tsx`, `frontend/src/lib/research-progress.ts`, and `frontend/src/lib/research-stream.ts`.
- Coverage in `backend/tests/unit/test_sse.py`, `frontend/tests/research-progress.test.mjs`, and `frontend/tests/research-progress.browser.py`. The local API E2E script also uses bearer auth. The frontend unit-test command includes progress recovery.
- API contract and incident documentation under `docs/`.

## Verification

- Backend suite passed 96 tests with a fail-fast tokenizer test substitute because Windows blocked the native DLL. The focused SSE regression also passed after adding the completion-during-connect assertion. The route tests cover owner access, cross-user denial, expired authentication, initial state, and terminal events.
- Frontend passed 11 unit tests, lint, TypeScript typecheck, and the Next.js production build.
- Local Chromium with synthetic API and auth fixtures verified the 404 state, actual question and progress, stream interruption, reload, and report navigation after persisted completion.

## Production limitations

The production probe confirmed the old stream's 401 response. An authenticated production run through submission, persisted session, live SSE, and completed report still requires deployment and an approved QA session. Existing background jobs and SSE events are process-local. The client recovers persisted stages after a disconnect. A backend process restart can still interrupt the job itself.
