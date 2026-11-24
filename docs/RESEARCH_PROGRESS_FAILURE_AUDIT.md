# Research progress failure audit

## Confirmed break

The active page opened a stream immediately after navigation. It sent an `Authorization: Bearer` header to `GET /api/v1/research/{research_id}/stream`. The deployed FastAPI route used a separate dependency that accepted only the `token` query parameter. It rejected the request before JWT validation or the session ownership lookup.

On November 24, 2026, a read-only probe of the Render endpoint with the Vercel origin, a synthetic session ID, and a deliberately invalid bearer value returned HTTP **401** with `MISSING_AUTH` and the message “Token query parameter is required for SSE connections.” Render returned the correct CORS origin. The backend request ID was `d6491842-c39c-4652-b1eb-3273ec7ffe95`. A valid header would take the same original path because that dependency never read it.

The page grouped 401, 403, and 404 into the same message and depended on the initial stream frame for its mode. It never requested the session detail and had no source for the research question. A stream rejection therefore left the generic heading and empty activity panel.

## Request and persistence contracts

| Step | Contract |
| --- | --- |
| New Research | The Next.js submission proxy forwards the authenticated request. FastAPI returns 202 with `data.research_id` after the session write. The page navigates using that UUID. |
| Session detail | `GET /api/v1/research/{id}` returns `data.id`, `data.question`, `data.config`, `data.status`, and the failure reason when present. |
| Session status | `GET /api/v1/research/{id}/status` returns `data.research_id`, `data.status`, and `data.iteration_count`. |
| SSE | The stream emits `status_update`, periodic `heartbeat`, and `done` for terminal work. It subscribes before its second session read so completion during connection setup can be observed. |
| Completion | The service writes the report before setting the session to completed. The report API reads the completed report for its owner. |

The confirmed authentication failure occurs before the stream checks ownership. There is no evidence that the incident was caused by a Supabase RLS rejection, an unsupported signing algorithm, an incorrect session ID, or an uncommitted session. The original user's authenticated browser trace and matching production logs were unavailable.
