# ResearchPilot AI — Backend

FastAPI backend for the ResearchPilot AI autonomous research platform.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- Supabase project (for database and auth)
- API keys: Google Gemini, Groq, Tavily

## Setup

### 1. Copy environment file and fill in values

```bash
cp ../.env.example .env
# Edit .env with your API keys
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Run the development server

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

## Available Endpoints (Phase 1A)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Liveness probe |
| GET | `/api/v1/readiness` | Readiness probe (checks Supabase) |
| POST | `/api/v1/research` | Submit research question |
| GET | `/api/v1/research` | List research history |
| GET | `/api/v1/research/{id}` | Get session detail |
| GET | `/api/v1/research/{id}/status` | Lightweight status poll |
| GET | `/api/v1/research/{id}/stream` | SSE event stream |
| GET | `/api/v1/research/{id}/report` | Get completed report |
| DELETE | `/api/v1/research/{id}` | Cancel or delete session |
| GET | `/api/v1/users/me` | Get user profile |
| PATCH | `/api/v1/users/me` | Update user profile |

> **Phase 1A Note:** Research submission creates a DB record and returns 202,
> but the LangGraph pipeline is not yet wired (Phase 1B). Sessions will
> immediately transition to `failed` with a "not yet implemented" message.

## Running Tests

```bash
uv run pytest tests/ -v
```

Tests do not require real API keys — all external services are mocked.

## Code Quality

```bash
# Format
uv run ruff format app/ tests/

# Lint
uv run ruff check app/ tests/

# Type check (optional, requires pyright or mypy)
uv run pyright app/
```

## Docker

```bash
# Build
docker build -t researchpilot-backend .

# Run (requires .env in current directory)
docker run --env-file .env -p 8000:8000 researchpilot-backend
```

## Architecture Notes

- All config via environment variables — never hardcode secrets
- All LLM calls must use `app.llm.router.LLMRouter` — no direct provider SDK imports
- Service layer owns business logic — route handlers are thin
- Supabase service role client is backend-only — never expose to frontend
- Rate limiting: in-memory per-user counters (MVP; Redis in Phase 3)

See `ARCHITECTURE.md`, `AGENTS.md`, and `V1_FREEZE.md` in the repository root for full architecture documentation.
