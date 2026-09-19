<div align="center">
  <h1>🚀 ResearchPilot AI</h1>
  <p><b>An autonomous multi-agent research platform for structured, verifiable, citation-backed intelligence.</b></p>
  
  [![Status](https://img.shields.io/badge/Status-MVP_Ready-blue.svg)]()
  [![Backend](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi)]()
  [![Frontend](https://img.shields.io/badge/Frontend-Next.js-000000.svg?logo=next.js)]()
  [![AI](https://img.shields.io/badge/AI-LangGraph-FF9900.svg)]()
  [![Database](https://img.shields.io/badge/Database-Supabase-3ECF8E.svg?logo=supabase)]()
</div>

---

## 🌟 Vision

Manual research is broken. Synthesizing information from multiple sources, verifying claims, tracing citations, and composing a coherent report takes hours. Most AI tools paper over this problem with faster hallucinations.

ResearchPilot AI treats research as a **structured, verifiable process**. 
- 🎯 **Grounded Claims:** Every claim is grounded in evidence.
- 🔗 **Traceable Sources:** Every evidence item is traceable to a source.
- ⚖️ **Credibility Ranking:** Every source is ranked for credibility.
- 🛡️ **Critical Verification:** A dedicated Critic Agent challenges every claim before it reaches the final report.

The goal is not faster research. It is **more trustworthy research**.

---

## 🏗️ Architecture & Workflow

ResearchPilot AI is orchestrated by LangGraph, routing dynamic tasks to specialized AI agents.

### System Architecture

```mermaid
graph TD
    %% Core Entities
    User((👤 User))
    
    subgraph Frontend [Next.js Frontend]
        UI[Web UI]
        AuthUI[Authentication]
    end
    
    subgraph Backend [FastAPI Backend]
        API[REST API & SSE]
        Auth[Auth Middleware]
    end
    
    subgraph MultiAgentSystem [LangGraph Research System]
        Planner[🧠 Planner Agent]
        WebRes[🌐 Web Research Agent]
        AcadRes[📚 Academic Agent]
        Ranker[⭐ Source Ranker]
        Extractor[✂️ Evidence Extractor]
        Synth[🧩 Synthesis Agent]
        Critic[⚖️ Critic Agent]
        Writer[📝 Writer Agent]
    end
    
    subgraph Infrastructure [Data & External Services]
        Supabase[(Supabase PostgreSQL)]
        Tavily[Tavily Search API]
        LLM[LLM Routers: Gemini / Groq / OpenRouter]
    end

    %% Flow
    User -->|Inputs Query| UI
    UI -->|API Request| API
    AuthUI -->|Auth| Supabase
    API -->|Triggers| Planner
    
    Planner -->|Decomposes Queries| WebRes
    Planner -->|Decomposes Queries| AcadRes
    
    WebRes -->|Fetches Data| Tavily
    AcadRes -->|Fetches Data| Tavily
    
    WebRes --> Ranker
    AcadRes --> Ranker
    
    Ranker --> Extractor
    Extractor --> Synth
    Synth --> Critic
    
    Critic -->|Unverified Claims| Planner
    Critic -->|Verified Claims| Writer
    
    Writer -->|Final Report| API
    API -->|SSE Stream| UI
    
    %% Connections to external
    MultiAgentSystem -.->|Calls| LLM
    Backend -.->|Saves State| Supabase
```

### Research Workflow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Backend
    participant Agents as LangGraph Agents
    participant External as LLMs & Tools
    
    User->>Frontend: Submits Research Question
    Frontend->>Backend: POST /api/v1/research
    Backend-->>Frontend: 202 Accepted (Task ID)
    
    Backend->>Agents: Initiate Research Graph
    activate Agents
    
    Agents->>External: Planner Agent breaks down question
    External-->>Agents: Sub-tasks generated
    
    par Parallel Research
        Agents->>External: Web Research Agent (Tavily)
        Agents->>External: Academic Research Agent (P1)
    end
    External-->>Agents: Raw Sources
    
    Agents->>External: Rank Sources & Extract Evidence
    External-->>Agents: Structured Evidence
    
    Agents->>External: Synthesize Claims
    External-->>Agents: Draft Claims
    
    Agents->>External: Critic Agent (Verification)
    alt Unverified Claims Found
        External-->>Agents: Failures Detected
        Agents->>Agents: Trigger Retry Loop (Gather more info)
    else All Claims Verified
        External-->>Agents: Pass
    end
    
    Agents->>External: Writer Agent Drafts Report
    External-->>Agents: Final Markdown Report
    deactivate Agents
    
    Backend->>Supabase: Save Final Report
    Backend->>Frontend: Stream Complete (SSE)
    Frontend->>User: Displays Verified Report
```

---

## ⚡ Current Status & Roadmap

```text
✅ Phase 0: Planning / Architecture — COMPLETED (Specification Frozen)
⏳ Phase 1: MVP Development         — READY TO START
🗓️ Phase 2: P1 Features             — NOT STARTED
🗓️ Phase 3: Production Hardening    — NOT STARTED
```

> **Note:** All documentation in this repository describes the intended system. **No application code has been implemented yet** (apart from infrastructural health checks).

### 🚀 MVP Features (Phase 1)
- ✦ Research question input with decomposition into sub-questions
- ✦ Parallel web research via Tavily
- ✦ Source credibility and relevance ranking
- ✦ Verbatim evidence extraction
- ✦ Claim synthesis from evidence
- ✦ Critic Agent claim verification
- ✦ Controlled research retry loop for unverified claims
- ✦ Citation-backed Markdown report generation
- ✦ Real-time research progress via Server-Sent Events (SSE)
- ✦ Markdown report export
- ✦ Research session history
- ✦ User authentication (email/password)

### 🔮 Future Features (Phase 2)
- ◦ Academic research via Semantic Scholar and arXiv
- ◦ Private document upload and RAG-based retrieval (Qdrant)
- ◦ PDF report export
- ◦ Research configuration (depth, source types, iterations)
- ◦ Agent activity transparency panel
- ◦ Contradiction highlighting in reports

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS |
| **Backend** | Python, FastAPI, LangGraph, LangChain, Pydantic |
| **Database** | Supabase (PostgreSQL + Auth) |
| **Vector DB** | Qdrant Cloud (P1) |
| **Primary LLM** | Google Gemini API |
| **Fallback LLMs**| Groq API, OpenRouter |
| **Web Research** | Tavily |
| **Academic** | Semantic Scholar, arXiv (P1) |
| **Observability**| Langfuse |
| **Deployments**  | Vercel (Frontend), Railway (Backend recommended) |
| **CI/CD & DevOps**| GitHub Actions, Docker |

---

## 📁 Repository Structure

```text
ResearchPilot AI/
├── frontend/          # Next.js frontend
├── backend/           # FastAPI backend
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

## ⚙️ Environment Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker (optional for local database)

### Quickstart

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_ORG/researchpilot-ai.git
   cd researchpilot-ai
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` with your actual API keys. See [`.env.example`](.env.example) for required variables.*

3. **Backend Setup** (After Phase 1)
   ```bash
   cd backend
   uv sync
   uv run uvicorn app.main:app --reload
   ```

4. **Frontend Setup** (After Phase 1)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 💰 Free-Tier Strategy

ResearchPilot AI is designed to run entirely on free-tier infrastructure during development:

| Service | Free Tier Summary |
|---------|-------------------|
| **Supabase** | 500MB DB, 1GB storage, 50K auth users |
| **Google Gemini** | Rate-limited free tier |
| **Groq / OpenRouter**| Free tier with rate limits / Free models |
| **Tavily** | 1,000 credits/month |
| **Qdrant Cloud** | 1 cluster, 1GB, 1M vectors (P1) |
| **Langfuse Cloud** | Generous free tier |
| **Vercel / Railway** | Next.js free tier / Starter allowances |

> **Note:** The free-tier architecture has limitations (e.g., single backend process, rate limits). The system is designed to scale beyond free tier without rewrites. See `ARCHITECTURE.md` for Scalability details.

---

## 🩺 Production Health Check

ResearchPilot AI provides two production-safe health monitoring endpoints:

- 🟢 **Liveness Probe (`GET /api/v1/health`)**:
  - Lightweight process check used by load balancers. Returns `HTTP 200` as long as the Python backend is alive. No external calls.

- 🔵 **Deep Health Probe (`GET /api/v1/health/deep`)**:
  - Verifies backend activity **and** read-only communication with Supabase PostgreSQL.
  - Executes a minimal read-only query (`SELECT id FROM research_sessions LIMIT 1`) with a bounded timeout (`5.0s`).
  - **Does NOT** trigger research pipelines, LLM calls, Tavily searches, or mutations.
  - Recommended interval for uptime monitors (like Better Uptime): **Every 4 to 6 hours**.

---

## 🛡️ Security & Testing

- **Security:**
  - API keys stored securely as environment variables.
  - Supabase Row-Level Security (RLS) enforces data isolation.
  - JWT tokens validated on every protected backend request.
  - Mitigations against prompt injections in place.
- **Testing:**
  - Strict requirement for unit tests on every agent, tool, and LLM router.
  - Integration tests run against isolated test databases.
  - *No fabricated test results allowed.*

---

## 📚 Documentation Index

| Document | Purpose |
|----------|---------|
| [PRD.md](docs/PRD.md) | Product requirements, features, success metrics, risks |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, agent design, data flow, security |
| [AGENTS.md](docs/AGENTS.md) | AI coding agent rules, folder structure, coding standards |
| [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Data model, table definitions, RLS strategy |
| [API_SPEC.md](docs/API_SPEC.md) | API contract, endpoints, SSE event format |
| [DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) | Color palette, typography, component patterns |
| [USER_FLOWS.md](docs/USER_FLOWS.md) | User journeys and flow diagrams |
| [UI_UX_SPEC.md](docs/UI_UX_SPEC.md) | UI/UX specifications and UI component plans |
| [V1_FREEZE.md](docs/V1_FREEZE.md) | Summary of the V1 specification freeze |
| [.env.example](.env.example) | Environment variable template with documentation |

---

## 🤝 Contributing

Before writing any code:
1. Read `AGENTS.md` — it defines the rules for all code contributions.
2. Read `ARCHITECTURE.md` — it defines what can and cannot be changed.
3. Read the relevant feature spec in `PRD.md`.

> Do not introduce new dependencies, frameworks, or services without updating `ARCHITECTURE.md` and receiving acknowledgment.

---
*License: TBD — to be determined before public launch.*
