# Phase 1K frontend stabilization

**PARTIAL.** Security and interaction fixes are implemented and covered by local
compilation and stream-parser checks. Authenticated browser regression, visual
comparison, and Web Vitals targets remain unverified.

## Changes

- Active research uses authenticated fetch streaming with the bearer token in
  the request header. Cleanup cancels reading and transport. There are three
  connection attempts with bounded delays, a 45-second read-idle watchdog,
  frame-size limits, terminal handling, and a capped activity log.
- Research submission has a synchronous pending guard, an idempotency key that
  survives retries for the same question, input bounds, a 30-second request
  deadline, and session-ID validation. Fast and Deep options remain available.
- Mobile navigation exposes Dashboard, History, Settings and logout. The layout
  uses the dynamic viewport height. Dashboard/history requests select needed
  fields, exclude deleted rows, and include the authenticated owner.
- Dashboard reports actual recent counts. History is paginated and unfinished
  sessions link to their status view. A route error boundary offers retry.
- Report requests abort on unmount or timeout, HTTP errors are visible, references
  permit HTTP/HTTPS only, and legacy raw UUIDs are removed from displayed prose.
  Legacy sources load only when needed. Current report API metadata supplies
  source details.
- Auth forms and profile updates use pending submit controls. Profile names are
  bounded, metadata failures report partial update, middleware redirects preserve
  refreshed cookies, and public landing/static assets skip auth middleware.
- Reduced-motion and visible focus styles preserve Sage colors and typography.

## Files

Changed routes under frontend/src/app include login, signup, dashboard layout,
dashboard, history, settings, report, active research and new research.
New dashboard loading/error boundaries and components/ui/SubmitButton.tsx supply
loading and retry feedback. Other changes include globals.css, middleware.ts,
lib/supabase/middleware.ts, lib/research-stream.ts, package.json, and
tests/research-stream.test.mjs.

## Validation

TypeScript, ESLint and the production build passed. Three Node tests passed for
fragmented CRLF stream frames, terminal delivery, malformed payloads, EOF and
aborted delivery. Run npm test from frontend to compile the parser into the
ignored scratch directory and run its tests. No backend files changed.

See [the audit](PHASE_1K_FRONTEND_AUDIT.md) and
[build comparison](../evaluation/results/frontend_performance_comparison.md).

## Remaining verification

Real authentication, session refresh, cross-user access, form submissions,
reconnection timing, settings persistence, report citations and mobile keyboard
navigation still need authenticated browser tests. Before/after screenshots at
375, 768, 1024 and 1440 pixels were not captured. Lighthouse/React Profiler
measurements remain pending. No claim of achieving LCP 2.5 s, INP 200 ms, CLS 0.1,
or Lighthouse 90 is supported by these local checks.

The report route still has sequential metadata and API fetching. Some existing
Link/Button combinations produce nested interactive elements and need a focused
accessibility follow-up. Settings writes span public profile and auth metadata
without a shared transaction; partial failure is surfaced. Initial stream
connection time depends on the backend and network. A browser-level form and
transport lifecycle suite is still required before acceptance.
