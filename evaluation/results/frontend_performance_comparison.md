# Phase 1K frontend performance comparison

Local Windows production builds, Next.js 14.2.35, Node 24.14.1, existing dependencies.

| First-load JavaScript | Baseline | After |
| --- | ---: | ---: |
| Shared | 87.3 kB | 87.3 kB |
| Report | 215 kB | 216 kB |
| Active research | 170 kB | 171 kB |
| New research | 170 kB | 171 kB |
| Login | 96.2 kB | 106 kB |

Pending server-action buttons add a client boundary. Streaming retry and parsing
adds code. These measurements establish a small bundle increase, not faster
rendering. No heavy dependency was added. Markdown remains statically loaded
because the report immediately needs it.

Dashboard fetches four columns for ten rows. History now fetches six columns for
twenty rows per page instead of all columns and unlimited rows. Report sources
are fetched only when legacy citation maps require them. Report metadata and API
requests are still sequential and remain a network optimization opportunity.

FCP, LCP, INP, CLS, TTFB, navigation latency, backend cold-start latency, React
render frequency and SSE delivery latency remain unmeasured. No Lighthouse score
or browser screenshot was captured. Authenticated desktop/mobile QA is pending.
