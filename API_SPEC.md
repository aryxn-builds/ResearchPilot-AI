# API_SPEC.md — API Contract Document

> **Status:** Specification Frozen
> **Version:** 1.0.0
> **Last Updated:** 2026-09-16
> **Owner:** ResearchPilot AI Project
>
> **Note:** This document defines the API contract. Actual FastAPI implementation has NOT started. This document is structured to be directly implementable as OpenAPI once development begins.

---

## Table of Contents

1. [API Principles](#api-principles)
2. [Authentication](#authentication)
3. [Common Response Format](#common-response-format)
4. [Error Format](#error-format)
5. [Research APIs](#research-apis)
6. [Document APIs (P1)](#document-apis-p1)
7. [User APIs](#user-apis)
8. [Pagination](#pagination)
9. [Rate Limiting](#rate-limiting)
10. [Idempotency](#idempotency)
11. [Async Research Jobs](#async-research-jobs)
12. [SSE — Server-Sent Events](#sse--server-sent-events)
13. [OpenAPI Compatibility](#openapi-compatibility)

---

## API Principles

| Principle | Implementation |
|-----------|----------------|
| **Versioned** | All endpoints are prefixed with `/api/v1/` |
| **JSON-first** | Request and response bodies are JSON (except SSE and file uploads) |
| **Authentication required** | All endpoints except health check require a valid JWT |
| **Consistent error format** | All errors return `{ "error": { "code": ..., "message": ..., "details": ... } }` |
| **HTTP semantics respected** | GET never mutates; POST creates; DELETE removes; PATCH updates |
| **Explicit status codes** | Each endpoint documents every possible status code |
| **Async by design** | Research is submitted as a job; clients poll or stream for status |
| **No server-side sessions** | Stateless; all identity from JWT |

---

## Authentication

All protected endpoints require a Bearer JWT token in the `Authorization` header.

```
Authorization: Bearer <supabase_access_token>
```

The token is issued by Supabase Auth after login. The backend validates the JWT using the Supabase JWT secret.

**Token Details:**

| Property | Value |
|----------|-------|
| **Algorithm** | HS256 (Supabase default) |
| **Issuer** | Supabase project URL |
| **Expiry** | 1 hour (Supabase default) |
| **Refresh** | Handled client-side via Supabase SDK |
| **Claims** | `sub` = user UUID; `email`; `role` |

**Authentication Errors:**

| Scenario | Status Code | Error Code |
|----------|-------------|------------|
| Missing Authorization header | 401 | `MISSING_AUTH` |
| Invalid or expired token | 401 | `INVALID_TOKEN` |
| Valid token, insufficient permissions | 403 | `FORBIDDEN` |

---

## Common Response Format

### Success Response

```json
{
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-09-16T12:00:00Z"
  }
}
```

For paginated responses:

```json
{
  "data": [ ... ],
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-09-16T12:00:00Z",
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 45,
      "total_pages": 3
    }
  }
}
```

### Accepted Response (202)

For async job submissions:

```json
{
  "data": {
    "research_id": "uuid",
    "status": "pending",
    "status_url": "/api/v1/research/{research_id}/status",
    "stream_url": "/api/v1/research/{research_id}/stream"
  },
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-09-16T12:00:00Z"
  }
}
```

---

## Error Format

All errors use a consistent structure:

```json
{
  "error": {
    "code": "RESEARCH_NOT_FOUND",
    "message": "Research session with the provided ID was not found.",
    "details": { }
  },
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-09-16T12:00:00Z"
  }
}
```

### Standard Error Codes

| HTTP Status | Error Code | Meaning |
|-------------|------------|---------|
| 400 | `VALIDATION_ERROR` | Request body or query param failed validation |
| 400 | `INVALID_QUESTION` | Research question is empty or exceeds character limit |
| 401 | `MISSING_AUTH` | No Authorization header |
| 401 | `INVALID_TOKEN` | JWT is invalid or expired |
| 403 | `FORBIDDEN` | Authenticated but not authorized for this resource |
| 404 | `NOT_FOUND` | Generic not found |
| 404 | `RESEARCH_NOT_FOUND` | Research session ID not found |
| 404 | `REPORT_NOT_FOUND` | Report not yet generated |
| 409 | `SESSION_ALREADY_EXISTS` | Idempotency key collision |
| 409 | `MAX_SESSIONS_REACHED` | User has reached concurrent session limit |
| 422 | `UNPROCESSABLE` | Request is valid JSON but semantically invalid |
| 429 | `RATE_LIMITED` | Rate limit exceeded |
| 500 | `INTERNAL_ERROR` | Unhandled server error |
| 503 | `RESEARCH_UNAVAILABLE` | All LLM providers are unavailable |

---

## Research APIs

### `POST /api/v1/research`

**Purpose:** Submit a new research question. Returns immediately with a research ID and stream URL. Research executes asynchronously.

**Authentication:** Required

**Rate Limit:** 3 concurrent sessions per user; 10 requests per hour per user (TBD — adjust after baseline)

**Request Body:**

```json
{
  "question": "What are the main mechanisms by which large language models can fail at multi-step reasoning?",
  "config": {
    "max_iterations": 2,
    "source_types": ["web"],
    "max_sources_per_task": 5
  }
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `question` | string | Yes | — | 10–1,000 characters |
| `config` | object | No | `{}` | All config fields are optional |
| `config.max_iterations` | integer | No | `2` | 1–3 |
| `config.source_types` | array of string | No | `["web"]` | Allowed: `web`, `academic` (P1), `rag` (P1) |
| `config.max_sources_per_task` | integer | No | `5` | 1–10 |

**Response: 202 Accepted**

```json
{
  "data": {
    "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "pending",
    "status_url": "/api/v1/research/3fa85f64-5717-4562-b3fc-2c963f66afa6/status",
    "stream_url": "/api/v1/research/3fa85f64-5717-4562-b3fc-2c963f66afa6/stream"
  },
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Errors:**

| Code | Status | Condition |
|------|--------|-----------|
| `VALIDATION_ERROR` | 400 | Invalid request body |
| `INVALID_QUESTION` | 400 | Question empty or too long |
| `MAX_SESSIONS_REACHED` | 409 | User has 3 in-progress sessions |
| `RATE_LIMITED` | 429 | Rate limit exceeded |

---

### `GET /api/v1/research/{research_id}`

**Purpose:** Retrieve full research session details including metadata and summary statistics.

**Authentication:** Required

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `research_id` | UUID | Research session ID |

**Response: 200 OK**

```json
{
  "data": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "question": "What are the main mechanisms...",
    "status": "completed",
    "config": { "max_iterations": 2, "source_types": ["web"] },
    "iteration_count": 1,
    "total_claims": 12,
    "verified_claims": 10,
    "started_at": "2026-09-16T12:00:00Z",
    "completed_at": "2026-09-16T12:01:23Z",
    "created_at": "2026-09-16T12:00:00Z"
  },
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Errors:**

| Code | Status | Condition |
|------|--------|-----------|
| `RESEARCH_NOT_FOUND` | 404 | ID not found or belongs to another user |

---

### `GET /api/v1/research/{research_id}/status`

**Purpose:** Lightweight status-only endpoint for polling. Returns only the status and progress fields.

**Authentication:** Required

**Response: 200 OK**

```json
{
  "data": {
    "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "verifying",
    "iteration_count": 1,
    "current_phase": "critic_verification",
    "progress_pct": 75
  },
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Status Values:** `pending`, `planning`, `researching`, `verifying`, `writing`, `completed`, `failed`, `cancelled`

**Errors:**

| Code | Status | Condition |
|------|--------|-----------|
| `RESEARCH_NOT_FOUND` | 404 | ID not found |

---

### `GET /api/v1/research/{research_id}/stream`

**Purpose:** Server-Sent Events stream for real-time research progress. Connect at research start; keep open until `event: done` or `event: error`.

**Authentication:** Required (JWT via query param `?token=<jwt>` since SSE does not support custom headers in all browsers)

> **Security Note:** Passing JWT as a query parameter is a known tradeoff for SSE. The token must be short-lived, and the backend must validate it on connection. Do not log query parameters containing tokens.

**Response:** `Content-Type: text/event-stream`

**Event Format:**

```
id: <event-id>
event: <event-type>
data: <json-payload>

```

**Event Types:**

| Event | When | Payload |
|-------|------|---------|
| `status_update` | When research phase changes | `{ "status": "planning", "phase": "planner_agent", "message": "Decomposing research question..." }` |
| `plan_created` | After Planner Agent completes | `{ "sub_question_count": 4, "sub_questions": ["...", "..."] }` |
| `research_started` | When parallel research begins | `{ "task_count": 4 }` |
| `task_completed` | When a research task completes | `{ "task_id": "...", "sub_question": "...", "source_count": 5 }` |
| `evidence_extracted` | After Evidence Extractor | `{ "evidence_count": 23 }` |
| `claims_generated` | After Synthesis Agent | `{ "claim_count": 12 }` |
| `verification_started` | When Critic Agent begins | `{ "iteration": 1, "claim_count": 12 }` |
| `verification_result` | After Critic Agent | `{ "iteration": 1, "verified": 10, "unverified": 2, "contradicted": 0 }` |
| `retry_started` | When targeted retry begins | `{ "iteration": 2, "reason": "2 unverified claims require additional research" }` |
| `writing_started` | When Writer Agent begins | `{ "verified_claim_count": 10 }` |
| `done` | Research complete | `{ "research_id": "...", "report_url": "/api/v1/research/{id}/report", "status": "completed" }` |
| `error` | Research failed | `{ "research_id": "...", "error_code": "PROVIDER_EXHAUSTED", "message": "..." }` |

**Client Behavior:**
- Connect to the stream URL after receiving 202 from `POST /api/v1/research`.
- Handle `event: done` and `event: error` to close the connection.
- Reconnect using `Last-Event-ID` header on disconnect.

---

### `GET /api/v1/research/{research_id}/report`

**Purpose:** Retrieve the completed research report.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | `json` | `json` (structured) or `markdown` (raw Markdown text) |

**Response: 200 OK (format=json)**

```json
{
  "data": {
    "research_id": "3fa85f64...",
    "generated_at": "2026-09-16T12:01:23Z",
    "content_markdown": "# Research Report\n\n## Introduction\n\n...",
    "citation_map": {
      "[1]": { "source_id": "uuid", "url": "https://...", "title": "..." },
      "[2]": { "source_id": "uuid", "url": "https://...", "title": "..." }
    },
    "total_citations": 8,
    "word_count": 1240,
    "section_count": 5,
    "summary": {
      "total_claims": 12,
      "verified_claims": 10,
      "excluded_claims": 2,
      "iterations": 1
    }
  },
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Response: 200 OK (format=markdown)**

```
Content-Type: text/markdown
Content-Disposition: attachment; filename="report-<research_id>.md"

# Research Report: What are the main mechanisms...

[Markdown content]
```

**Errors:**

| Code | Status | Condition |
|------|--------|-----------|
| `RESEARCH_NOT_FOUND` | 404 | Session not found |
| `REPORT_NOT_FOUND` | 404 | Session exists but report not yet generated (still in progress) |

---

### `DELETE /api/v1/research/{research_id}`

**Purpose:** Cancel an in-progress research session or delete a completed session. Soft-deletes the record.

**Authentication:** Required

**Behavior:**
- If `status` is `pending`, `planning`, `researching`, `verifying`, or `writing`: cancels the session (status → `cancelled`).
- If `status` is `completed` or `failed`: soft-deletes the record (`deleted_at` is set).

**Response: 200 OK**

```json
{
  "data": {
    "research_id": "3fa85f64...",
    "status": "cancelled"
  },
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Errors:**

| Code | Status | Condition |
|------|--------|-----------|
| `RESEARCH_NOT_FOUND` | 404 | Session not found |
| `FORBIDDEN` | 403 | Session belongs to another user |

---

### `GET /api/v1/research`

**Purpose:** List the authenticated user's research sessions (history).

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | `1` | Page number |
| `page_size` | integer | `20` | Results per page (max 50) |
| `status` | string | — | Filter by status |

**Response: 200 OK**

```json
{
  "data": [
    {
      "id": "uuid",
      "question": "What are the main mechanisms...",
      "status": "completed",
      "verified_claims": 10,
      "total_claims": 12,
      "created_at": "2026-09-16T12:00:00Z",
      "completed_at": "2026-09-16T12:01:23Z"
    }
  ],
  "meta": {
    "request_id": "...",
    "timestamp": "...",
    "pagination": { "page": 1, "page_size": 20, "total": 5, "total_pages": 1 }
  }
}
```

---

## Document APIs (P1)

> These endpoints are P1 features. Do not implement them for MVP.

### `POST /api/v1/documents`

**Purpose:** Upload a document for private RAG research.

**Authentication:** Required

**Request:** `multipart/form-data`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `file` | file | Yes | PDF, TXT, DOCX; max 10MB (TBD) |
| `display_name` | string | No | Optional friendly name |

**Response: 202 Accepted** — Document processing begins asynchronously.

```json
{
  "data": {
    "document_id": "uuid",
    "filename": "research-paper.pdf",
    "status": "processing",
    "status_url": "/api/v1/documents/{document_id}"
  }
}
```

---

### `GET /api/v1/documents`

**Purpose:** List user's uploaded documents.

**Authentication:** Required

---

### `DELETE /api/v1/documents/{document_id}`

**Purpose:** Delete a document and its associated vector embeddings.

**Authentication:** Required

---

## User APIs

### `GET /api/v1/users/me`

**Purpose:** Retrieve the authenticated user's profile.

**Authentication:** Required

**Response: 200 OK**

```json
{
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "Jane Researcher",
    "preferences": {},
    "created_at": "2026-09-16T10:00:00Z"
  }
}
```

---

### `PATCH /api/v1/users/me`

**Purpose:** Update user profile fields.

**Authentication:** Required

**Request Body:** (all fields optional)

```json
{
  "display_name": "Jane R."
}
```

**Response: 200 OK** — Updated user profile.

---

### `GET /api/v1/health`

**Purpose:** Health check endpoint. No authentication required.

**Response: 200 OK**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2026-09-16T12:00:00Z"
}
```

---

## Pagination

All list endpoints support cursor-based or offset-based pagination.

**MVP:** Offset-based pagination.

| Parameter | Type | Default | Max |
|-----------|------|---------|-----|
| `page` | integer | 1 | — |
| `page_size` | integer | 20 | 50 |

Response `meta.pagination` always includes `total` and `total_pages`.

---

## Rate Limiting

| Endpoint | Limit | Window | Per |
|----------|-------|--------|-----|
| `POST /api/v1/research` | 10 requests | 1 hour | User |
| `POST /api/v1/research` | 3 concurrent | Active at once | User |
| `GET /api/v1/research/*` | 120 requests | 1 minute | User |
| `POST /api/v1/documents` | 20 requests | 1 hour | User |
| All other endpoints | 60 requests | 1 minute | User |

Rate limit headers returned on every response:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1726488000
```

When exceeded: `429 Too Many Requests` with `Retry-After` header.

> **Adjust limits after baseline measurement. Do not treat these as final production values.**

---

## Idempotency

`POST /api/v1/research` supports idempotency via an optional header:

```
Idempotency-Key: <client-generated-uuid>
```

If a request with the same `Idempotency-Key` is received within 24 hours, the original response is returned without starting a new research session.

Idempotency keys are stored with the session and expire after 24 hours.

---

## Async Research Jobs

Research is a long-running operation (typically 30–120 seconds). The API design handles this explicitly:

### Job Lifecycle

```
1. Client POSTs /api/v1/research
2. Server creates session record (status: pending)
3. Server returns 202 with { research_id, status_url, stream_url }
4. Server starts async research job
5. Client connects to stream_url (SSE)
6. Client receives progress events
7. On event: done → client fetches report from report_url
8. On event: error → client reads error details from status_url
```

### Timeout Behavior

| Scenario | Behavior |
|----------|----------|
| Research takes > 5 minutes | Session marked `failed`; `error` SSE event sent |
| Client disconnects from SSE | Research continues in background |
| Client reconnects to SSE | Catches up from `Last-Event-ID` |
| Server restarts during research | Session remains in database with last known status; reconnect may show stale state |

> **Note:** Session recovery after server restart is not implemented for MVP (in-process asyncio tasks). Plan for Celery migration before production scale.

---

## SSE — Server-Sent Events

### Connection

```
GET /api/v1/research/{research_id}/stream?token=<jwt>
Accept: text/event-stream
Cache-Control: no-cache
```

### Stream Format

Each event follows the SSE specification:

```
id: 1
event: status_update
data: {"status":"planning","phase":"planner_agent","message":"Decomposing research question into sub-questions..."}

id: 2
event: plan_created
data: {"sub_question_count":4,"sub_questions":["What are attention-based failure modes?","How does chain-of-thought affect reasoning?","What are known prompting failure patterns?","How do benchmark saturations affect evaluation?"]}

id: 3
event: research_started
data: {"task_count":4}

...

id: 15
event: done
data: {"research_id":"3fa85f64...","status":"completed","report_url":"/api/v1/research/3fa85f64.../report"}
```

### Heartbeat

The server sends a comment every 15 seconds to keep the connection alive:

```
: heartbeat

```

### Reconnection

On disconnect, the client sends `Last-Event-ID` header. The server replays missed events from the event log. Events are stored for the duration of the active research session only.

---

## OpenAPI Compatibility

This specification is structured so it can be generated as an OpenAPI 3.1 document.

FastAPI automatically generates OpenAPI JSON at `/openapi.json` and interactive docs at `/docs`.

When implementing:
- Use Pydantic models for all request/response bodies.
- Use `response_model` on all FastAPI endpoints.
- Add `summary`, `description`, and `tags` to every route decorator.
- Use `HTTPException` with documented status codes only.

The OpenAPI YAML will be auto-generated from FastAPI; do not maintain a separate YAML file.
