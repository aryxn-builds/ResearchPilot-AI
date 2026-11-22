# Supabase keep-alive and health monitoring

## Purpose

Supabase Free projects can pause after low database activity over a seven-day period.
This workflow performs approximately four real database reads per day to help reduce
that risk and detect backend/database failures. Supabase controls inactivity detection:
a few database requests per day are usually sufficient, but **do not guarantee** that
a Free project will remain active. See [Supabase project pausing](https://supabase.com/docs/guides/platform/free-project-pausing).

## Architecture

```text
GitHub Actions -> HTTPS -> Render FastAPI -> Supabase PostgreSQL
                          GET /api/v1/health/deep
```

The existing endpoint in `backend/app/api/v1/health.py` calls
`check_database_connectivity()` in `backend/app/core/database.py` on every authorized
request. It reuses the singleton service client and awaits
`table("research_sessions").select("id").limit(1).execute()` with the existing
database timeout (default five seconds). An empty table is a successful read.
Only the client is reused; query results are not cached. The monitor sends a
`Cache-Control: no-cache, no-store` request header; do not configure a proxy/CDN to
cache this endpoint. Use the Render origin directly.

No inserts, updates, deletes, dummy users, research pipelines, LangGraph agents,
LLMs or Tavily searches are invoked. Database credentials remain on the backend.
The endpoint and its timeout are unchanged by this automation.

## Configuration

In GitHub, open **Settings -> Secrets and variables -> Actions**:

| Kind | Name | Value |
| --- | --- | --- |
| Repository variable | `RESEARCHPILOT_BACKEND_URL` | Render HTTPS base URL, e.g. `https://example-backend.onrender.com`, without a trailing slash or `/api/v1` |
| Repository secret | `HEALTH_CHECK_SECRET` | Exactly the same value as the backend's `HEALTH_CHECK_SECRET`, if enabled |

Use a dedicated, randomly generated health secret (for example a 32-byte hex value).
Set it in the Render backend environment and in GitHub's repository secrets. Allow
Render to apply that environment change before testing. Never put the value in a
commit, command output, issue, or workflow file. Do not use a Supabase service-role
key, personal access token, deployment credential, or user JWT here.

If the endpoint is intentionally public, leave `HEALTH_CHECK_SECRET` unset in both
places. The workflow then omits the Authorization header. If the backend requires
authentication but GitHub has a missing or different secret, the run fails on 401
without retrying. Secrets must be single-line printable ASCII without surrounding
whitespace. Only HTTPS origins on the default HTTPS port are accepted; credentials,
paths, query strings and fragments are rejected.

These GitHub settings are not read from the repository `.env` file. No new backend
configuration or database/RLS changes are necessary.

## Schedule and request behavior

The workflow is `.github/workflows/supabase-keepalive.yml`, named
**Supabase Keep-Alive & Health Monitor**.

- UTC cron: `17 */6 * * *` — **00:17, 06:17, 12:17 and 18:17 UTC**, every day.
- Scheduled runs use the default branch. Manual runs must select that branch too;
  the job skips manual runs targeting other branches.
- A shared concurrency group allows only one active execution, without cancelling
  an active check. GitHub may replace an older pending run with a newer pending run.
- Connection timeout: 15 seconds; total curl request timeout: 120 seconds.
  An outer 125-second process timeout protects against a stuck curl process.
- Maximum three attempts, with 20 seconds between attempts; job timeout: 10 minutes.
- Retry DNS/connection failures, timeouts, interrupted connections and HTTP 502/503/504.
  Authentication errors, other HTTP failures, TLS verification errors and invalid
  HTTP 200 health responses fail immediately.
- TLS verification stays enabled, HTTPS is enforced, redirects are rejected, and
  curl's user configuration is disabled. Response size is limited to 64 KiB.
- No packages are installed. Python's standard library validates curl's response.
  The bearer header is supplied through stdin, never a command-line argument.

These timeouts accommodate Render cold starts; they do not change the database
query timeout, prevent Render sleeping, or restart the backend.

## Publish and manually test

1. Commit the workflow, tests and documentation on a feature branch, push it, and
   merge the reviewed change into the repository's default branch (currently `main`).
   For example, from the repository root:

   ```bash
   git switch -c feature/supabase-keepalive
   git add .github/workflows/supabase-keepalive.yml .github/tests/test_supabase_keepalive.py backend/tests/test_health.py docs/SUPABASE_KEEPALIVE.md README.md .env.example
   git commit -m "feat: add Supabase keep-alive health monitor"
   git push -u origin feature/supabase-keepalive
   ```

2. Configure the repository variable and optional matching secret above. Ensure
   GitHub Actions is enabled for the repository and the backend is deployed with
   the existing deep-health endpoint.
3. Open **Actions -> Supabase Keep-Alive & Health Monitor -> Run workflow**.
   Select the default branch and click **Run workflow**.
4. Open the run and inspect its summary. Success requires HTTP 200 and all fields:

   ```json
   {"status":"healthy","backend":"ok","database":"ok"}
   ```

   Expected summary: **PASS**, backend `ok`, Supabase `ok`, HTTP `200`, a UTC
   timestamp, last-attempt duration in seconds, and 1–3 attempts. The full response
   and sensitive headers are never printed. An unavailable database returns HTTP
   503 and fails after the allowed retries.
5. Failure produces a nonzero step exit, a red failed run, and **FAIL** in the
   summary. Check Actions notification preferences if you want failure emails;
   this workflow does not configure external alerts. A forcibly cancelled job or
   runner failure can prevent summary creation; the run status remains authoritative.

Local validation (from the repository root, with Python and PyYAML available in
your test environment; PyYAML is only needed to parse YAML in the tests):

```bash
python -m unittest discover -s .github/tests -p 'test_supabase_keepalive.py' -v
cd backend
python -m pytest tests/test_health.py -q
```

Use the backend virtual environment's Python if necessary. The workflow tests parse
the YAML and execute the actual embedded Python with mocked curl responses. They
cover configuration, scheduling, secret/public modes, HTTPS settings, retry limits,
recovery, auth rejection, malformed/missing/unhealthy fields, timeouts and output
redaction. Backend regression tests verify fresh read-only queries on repeated
requests. All tests use mocks, not live Supabase, Render or GitHub executions.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Backend 502/503/504 | Allow the bounded retries for a Render cold start. If persistent, inspect Render service health and backend logs privately; verify Supabase is active. |
| Timeout or unreachable backend | Check the Render hostname, deployment status and network availability. A cold start exceeding 120 seconds can exhaust retries. |
| HTTP 401/403 | Match the GitHub secret to Render's `HEALTH_CHECK_SECRET`; apply the backend environment update. Do not paste secrets into logs. |
| Supabase paused | Restore it manually in the Supabase dashboard, wait for readiness, then rerun. This workflow cannot restore paused projects. |
| GitHub Actions disabled or no recent runs | Check the Actions page, repository policy, usage limits and scheduled-workflow inactivity status; re-enable the workflow if needed. |
| Missing/invalid configuration; zero attempts | Set the repository variable under Actions **Variables**, using just the HTTPS origin; check secret formatting. |
| Malformed response or HTTP 200 with missing/failed fields | Confirm the URL targets FastAPI rather than the frontend, proxy/login page or liveness endpoint. Check deployed endpoint version; all three fields are required. |
| Backend/Supabase `unknown` | The response did not establish that component's health (e.g. no response, auth failure or malformed JSON). HTTP 000 means no HTTP status was captured. |
| Manual run skipped | Select the repository default branch. |

## Limitations

- [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
  run on the default branch and may be delayed or missed. The non-zero minute
  reduces top-of-hour contention but is not an execution guarantee.
- Public repository scheduled workflows may be disabled after **60 days of
  repository inactivity**. Monitor and re-enable them as necessary. This solution
  does not manufacture repository activity through automatic commits.
- A successful check proves connectivity at that moment; it does not guarantee
  Supabase will never pause or that the application stays continuously available.
- This does not automatically restore an already paused project and uses no
  privileged Supabase management tokens.
- When guaranteed prevention of **inactivity pausing** is required, use a paid
  Supabase plan; this is not a guarantee against all outages. See the
  [Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod).
- Local validation is not evidence of a successful deployed or scheduled run.
  Verify the first manual run and subsequent scheduled runs in GitHub Actions.
