# ResearchPilot AI

> **Current Status: Specification Frozen — Ready for MVP Development. No application code exists yet.**

An autonomous multi-agent research platform that accepts a complex question, investigates it using parallel AI agents across web and academic sources, verifies every claim, and delivers a structured, citation-backed report.

---

## Vision

Manual research is broken. Synthesizing information from multiple sources, verifying claims, tracing citations, and composing a coherent report takes hours. Most AI tools paper over this problem with faster hallucinations.

ResearchPilot AI treats research as a **structured, verifiable process**. Every claim is grounded in evidence. Every evidence item is traceable to a source. Every source is ranked for credibility. A dedicated Critic Agent challenges every claim before it reaches the final report.

The goal is not faster research. It is **more trustworthy research**.

---

## Current Status

```
Phase 0: Planning / Architecture — COMPLETED (Specification Frozen)
Phase 1: MVP Development         — READY TO START
Phase 2: P1 Features             — NOT STARTED
Phase 3: Production Hardening    — NOT STARTED
```

All documentation in this repository describes the intended system. **No implementation has been built.** Do not assume any code, API, database, or deployment is functional.

---

## Planned Features

### MVP (Phase 1)

- ✦ Research question input with decomposition into sub-questions
- ✦ Parallel web research via Tavily
- ✦ Source credibility and relevance ranking
- ✦ Verbatim evidence extraction
- ✦ Claim synthesis from evidence
- ✦ Critic Agent claim verification
- ✦ Controlled research retry loop for unverified claims
- ✦ Citation-backed Markdown report generation
- ✦ Real-time research progress via Server-Sent Events
- ✦ Markdown report export
- ✦ Research session history
- ✦ User authentication (email/password)

### Phase 2 (P1 Features)

- ◦ Academic research via Semantic Scholar and arXiv
- ◦ Private document upload and RAG-based retrieval
- ◦ PDF report export
- ◦ Research configuration (depth, source types, iterations)
- ◦ Agent activity transparency panel
- ◦ Contradiction highlighting in reports

---

## Architecture Overview

ResearchPilot AI is a multi-agent system orchestrated by LangGraph.

```
User → Next.js Frontend → FastAPI Backend → LangGraph Research Graph
                                                      ↓
                                              Planner Agent
                                                      ↓
                                         Parallel Research Agents
                                      Web | Academic (P1) | RAG (P1)
                                                      ↓
                                              Source Ranking
                                                      ↓
                                           Evidence Extraction
                                                      ↓
                                            Claim Synthesis
                                                      ↓
                                            Critic Verification
                                                      ↓
                                    (Retry loop if unverified claims)
                                                      ↓
                                            Writer Agent
                                                      ↓
                                         Citation-backed Report
```

Every LLM call goes through a provider router (Gemini → Groq → OpenRouter). No agent is coupled to a specific LLM provider.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS |
| **Backend** | Python, FastAPI, LangGraph, LangChain, Pydantic |
| **Database** | Supabase (PostgreSQL + Auth) |
| **Vector DB** | Qdrant Cloud (P1) |
| **Primary LLM** | Google Gemini API |
| **Fallback LLM** | Groq API |
| **Secondary Fallback** | OpenRouter |
| **Web Research** | Tavily |
| **Academic Research** | Semantic Scholar, arXiv (P1) |
| **Observability** | Langfuse |
| **Frontend Deploy** | Vercel |
| **Backend Deploy** | TBD — Railway recommended (see ARCHITECTURE.md ADL-007) |
| **CI/CD** | GitHub Actions |
| **Containerization** | Docker |

---

## Repository Structure

```
ResearchPilot AI/
├── frontend/          # Next.js frontend (not yet implemented)
├── backend/           # FastAPI backend (not yet implemented)
│   ├── app/
│   │   ├── api/       # HTTP endpoints
│   │   ├── agents/    # Research agents
│   │   ├── graph/     # LangGraph state machine
│   │   ├── tools/     # External API wrappers
│   │   ├── llm/       # LLM provider abstraction
│   │   ├── services/  # Application services
│   │   ├── schemas/   # Pydantic data models
│   │   ├── models/    # Database models
│   │   ├── core/      # Config, security, logging
│   │   └── prompts/   # LLM prompt templates
│   └── tests/
├── evaluation/        # Research quality evaluation scripts
├── docs/              # Specifications and technical documentation
│   ├── AGENTS.md          # AI Coding Agent Instruction Manual
│   ├── API_SPEC.md        # API Contract Document
│   ├── ARCHITECTURE.md    # System Architecture Document
│   ├── DATABASE_SCHEMA.md # Database Schema Document
│   ├── DESIGN_SYSTEM.md   # Design System Document
│   ├── PRD.md             # Product Requirements Document
│   ├── UI_UX_SPEC.md      # UI/UX Specification
│   ├── USER_FLOWS.md      # User Journey Document
│   ├── V1_FREEZE.md       # V1 Specification Freeze
│   └── decisions/         # Architecture Decision Records
├── .github/workflows/ # CI/CD pipelines
└── .env.example       # Environment variable template
```

---

## Development Roadmap

### Phase 0 — Planning and Architecture (Completed)

- [x] Product Requirements Document (docs/PRD.md)
- [x] System Architecture Document (docs/ARCHITECTURE.md)
- [x] AI Coding Agent Instructions (docs/AGENTS.md)
- [x] Database Schema Design (docs/DATABASE_SCHEMA.md)
- [x] API Contract (docs/API_SPEC.md)
- [x] Design System (docs/DESIGN_SYSTEM.md)
- [x] User Flows (docs/USER_FLOWS.md)
- [x] Environment variable template (.env.example)
- [x] UI/UX Specification (docs/UI_UX_SPEC.md)
- [x] Architecture Decision Records (docs/decisions/ARCHITECTURE_DECISIONS.md)
- [x] V1 Specification Freeze (docs/V1_FREEZE.md)

### Phase 1 — MVP Development

- [ ] Backend project setup (FastAPI, LangGraph, Pydantic)
- [ ] LLM provider abstraction layer (Gemini + Groq + OpenRouter)
- [ ] Tavily web research tool
- [ ] Planner Agent
- [ ] Web Research Agent
- [ ] Source Ranker
- [ ] Evidence Extractor
- [ ] Synthesis Agent
- [ ] Critic Agent
- [ ] Writer Agent
- [ ] LangGraph research graph with controlled loop
- [ ] Database migrations (Supabase)
- [ ] FastAPI endpoints (`/research`, `/research/{id}`, `/research/{id}/stream`, `/research/{id}/report`)
- [ ] SSE streaming for research progress
- [ ] User authentication (Supabase Auth integration)
- [ ] Next.js frontend — auth pages
- [ ] Next.js frontend — research input and progress page
- [ ] Next.js frontend — report view and export
- [ ] Next.js frontend — research history
- [ ] Langfuse observability integration
- [ ] Unit tests for agents and tools
- [ ] GitHub Actions CI (lint, typecheck, tests)
- [ ] Docker deployment

### Phase 2 — P1 Features

- [ ] Academic research agents (Semantic Scholar, arXiv)
- [ ] Private document upload and processing
- [ ] Qdrant RAG agent
- [ ] PDF export
- [ ] Research configuration UI
- [ ] Agent activity transparency panel

### Phase 3 — Production Hardening

- [ ] Background job queue (Celery + Redis) to replace asyncio tasks
- [ ] Horizontal backend scaling
- [ ] Performance baseline and optimization
- [ ] Rate limiting enforcement
- [ ] Security audit
- [ ] Monitoring and alerting

---

## Environment Setup

> **Note:** The application is not yet implemented. These steps will be valid once Phase 1 is complete.

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional for local database)

### Step 1: Clone the repository

```bash
git clone https://github.com/YOUR_ORG/researchpilot-ai.git
cd researchpilot-ai
```

### Step 2: Configure environment variables

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

See [`.env.example`](.env.example) for all required variables and where to obtain them.

The following API keys are required to run the MVP:

| Service | URL | Free Tier |
|---------|-----|-----------|
| Google Gemini | https://aistudio.google.com/app/apikey | Yes |
| Groq | https://console.groq.com/keys | Yes |
| Tavily | https://tavily.com | Yes |
| Supabase | https://supabase.com | Yes |

> **Verify current free-tier limits before deployment.**

### Step 3: Backend setup

```bash
cd backend
# Commands to be documented after Phase 1 implementation
```

### Step 4: Frontend setup

```bash
cd frontend
# Commands to be documented after Phase 1 implementation
```

---

## Free-Tier Strategy

ResearchPilot AI is designed to run entirely on free-tier infrastructure during development and early validation.

| Service | Free Tier Summary |
|---------|-------------------|
| Supabase | 500MB DB, 1GB storage, 50K auth users |
| Google Gemini | Rate-limited free tier (verify current limits) |
| Groq | Free tier with rate limits |
| OpenRouter | Free models available |
| Tavily | 1,000 credits/month |
| Qdrant Cloud | 1 cluster, 1GB, 1M vectors (P1) |
| Langfuse Cloud | Free tier available (verify limits) |
| Vercel | Generous free tier for Next.js |
| Railway | Free tier (verify current terms) |

**The free-tier architecture has known limitations:**
- In-process asyncio tasks are lost on server restart
- Single backend process limits concurrency
- Rate limits may constrain burst usage

The architecture is designed to scale beyond free tier without rewrites. See `ARCHITECTURE.md → Scalability`.

---

## Security

- All API keys stored as environment variables; never in source code
- Frontend receives only the Supabase anon key; all other secrets are backend-only
- Supabase Row-Level Security enforces user data isolation at the database level
- JWT tokens validated on every protected backend request
- User research data is isolated and inaccessible to other users
- Research question inputs are wrapped in structured prompts to mitigate prompt injection

See `ARCHITECTURE.md → Security Architecture` for full details.

---

## Testing Strategy

- **Unit tests:** Every agent, tool, and LLM router component has unit tests with mocked external services
- **Integration tests:** Optional; use a test Supabase database; not run in CI by default
- **No fabricated test results:** Tests are either passing or failing; no invented metrics

See `AGENTS.md → Testing Rules` for the testing policy enforced on all contributors.

---

## Deployment Strategy

- **Frontend:** Vercel — automatic deployment on merge to `main`
- **Backend:** TBD (Railway recommended) — Docker container deployed via GitHub Actions
- **Database:** Supabase Cloud — no self-hosting for MVP
- **CI/CD:** GitHub Actions — lint, typecheck, unit tests on every PR

See `ARCHITECTURE.md → Deployment Architecture` and ADL-007 for backend hosting decision.

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [PRD.md](docs/PRD.md) | Product requirements, features, success metrics, risks |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, agent design, data flow, security |
| [AGENTS.md](docs/AGENTS.md) | AI coding agent rules, folder structure, coding standards |
| [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Data model, table definitions, RLS strategy |
| [API_SPEC.md](docs/API_SPEC.md) | API contract, endpoints, SSE event format |
| [DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) | Color palette, typography, component patterns |
| [USER_FLOWS.md](docs/USER_FLOWS.md) | User journeys and flow diagrams |
| [UI_UX_SPEC.md](docs/UI_UX_SPEC.md) | UI/UX specifications and Stitch component plans |
| [V1_FREEZE.md](docs/V1_FREEZE.md) | Summary of the V1 specification freeze |
| [.env.example](.env.example) | Environment variable template with documentation |

---

## Contributing

This project is in the planning phase. Before writing any code:

1. Read `AGENTS.md` — it defines the rules for all code contributions.
2. Read `ARCHITECTURE.md` — it defines what can and cannot be changed.
3. Read the relevant feature spec in `PRD.md`.

Do not introduce new dependencies, frameworks, or services without updating `ARCHITECTURE.md` and receiving acknowledgment.

---

## License

TBD — license to be determined before public launch.
