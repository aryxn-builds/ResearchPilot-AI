# Phase 1K frontend audit

| File or route | Evidence | Severity | Correction / verification |
| --- | --- | --- | --- |
| Active research | JWT in EventSource query URL, asynchronous setup after cleanup, unbounded activity array, immediate stop on transport errors | P1 | Authorization fetch, abort, bounded retries and activity. Test frames and terminals. |
| New research | React loading state alone guards submission; no timeout or response ID validation | P1 | Synchronous guard, idempotency key, timeout and response checks |
| Report | Sequential metadata/API/sources requests, no abort, direct reference href bypasses Markdown filtering | P1 | Abort, explicit HTTP failures, legacy-only source request, reference allowlist |
| Mobile layout | Sidebar hidden, header has only Dashboard and New | P1 | Add History, Settings and logout |
| Dashboard | Hardcoded ~2.5 min, at-most-ten rows called total reports, select(*), errors become empty state | P1 | Honest recent metrics, explicit owned live rows and error boundary |
| History | Unbounded select(*), no deleted filter, all statuses link to report | P2 | Paginate selected fields, status-aware navigation |
| Settings | Auth metadata update errors ignored, unlimited display name | P2 | Check partial failure, validate name length |
| Middleware | Refreshed cookies omitted from redirect; landing/fonts trigger auth | P2 | Preserve cookies, route-specific matcher |
| Auth forms | No pending submit feedback | P2 | useFormStatus button |
| CSS | No reduced motion override or global link focus | P2 | Add targeted accessibility rules |

No measured React render-count evidence supports blanket memoization. Existing Supabase browser factory uses the SDK's singleton behavior. Approved colors and fonts remain configured.

Historical production baseline from Phase 1J was shared JS 87.3 kB, report 215 kB, active 170 kB, new 170 kB. A fresh pre-edit build was started in Phase 1K. Browser Web Vitals and screenshots were not captured before editing. Read-only code findings must not be interpreted as measured backend latency.
