# PRD.md — Product Requirements Document

> **Status:** Specification Frozen
> **Version:** 1.0.0
> **Last Updated:** 2026-09-16
> **Owner:** ResearchPilot AI Project

---

## Table of Contents

1. [Product Overview](#product-overview)
2. [Target Users](#target-users)
3. [User Problems](#user-problems)
4. [Core Value Proposition](#core-value-proposition)
5. [Core Features](#core-features)
6. [MVP Definition](#mvp-definition)
7. [Non-Goals](#non-goals)
8. [Functional Requirements](#functional-requirements)
9. [Non-Functional Requirements](#non-functional-requirements)
10. [Success Metrics](#success-metrics)
11. [Risks](#risks)

---

## Product Overview

### Product Name

**ResearchPilot AI**

### One-Line Description

An autonomous multi-agent research platform that accepts a complex question, investigates it using parallel AI agents across web and academic sources, verifies every claim it makes, and delivers a structured, citation-backed report.

### Product Vision

To replace hours of manual research with a trustworthy, transparent, and auditable AI research workflow — one where the user can see exactly where every claim came from and how it was verified.

### Problem Being Solved

Current AI research tools either:
- Return hallucinated answers with no citations
- Retrieve web snippets with no synthesis or claim verification
- Require users to manually search, synthesize, and cross-reference multiple sources
- Cannot distinguish between a supported claim and an unsupported assertion

ResearchPilot AI treats research as a structured, verifiable process — not a single LLM call.

---

## Target Users

### Primary Users

| User Type | Description | Research Context |
|-----------|-------------|-----------------|
| **Graduate Students / Academics** | Writing literature reviews, thesis research, survey papers | Academic depth, citation quality matters |
| **Developers / AI Engineers** | Researching technical approaches, comparing libraries, understanding papers | Technical accuracy, code relevance |
| **Analysts / Consultants** | Market research, competitive analysis, policy research | Synthesis quality, breadth of sources |
| **Knowledge Workers** | Researching topics for reports, decisions, briefings | Clarity, citation traceability |

### Secondary Users

| User Type | Description |
|-----------|-------------|
| **Independent Researchers** | Hobbyists and independent practitioners doing deep topic research |
| **Content Creators** | Writers and journalists needing verified, sourced background material |

> **Out of scope:** Enterprise teams, legal discovery, regulated industries (medical/legal advice). See [Non-Goals](#non-goals).

---

## User Problems

### The Current Research Workflow Is Broken

A user trying to answer a complex research question today must:

1. **Manually formulate multiple sub-questions** — complex topics require decomposition that users rarely do systematically.
2. **Search across multiple platforms** — Google, Google Scholar, arXiv, Semantic Scholar, Reddit, Wikipedia, etc.
3. **Read and skim dozens of documents** — manually extracting relevant sentences and facts.
4. **Maintain fragmented notes** — evidence is scattered across tabs, documents, and tools.
5. **Manually cross-reference claims** — no automated contradiction detection.
6. **Manually verify source quality** — distinguishing peer-reviewed papers from blog posts.
7. **Manually compose citations** — no automated citation management during synthesis.
8. **Manually write the synthesis** — with no guarantee of claim-evidence alignment.

### Key Pain Points

| Pain Point | Impact |
|-----------|--------|
| No claim-evidence traceability | Researcher cannot audit which claim came from which source |
| Manual source credibility assessment | Poor-quality sources can corrupt the output |
| No contradiction detection | Opposing evidence is missed or ignored |
| Repetitive boilerplate research | Same exploratory work repeated for similar topics |
| Slow multi-source synthesis | Hours of work for a multi-source synthesis |
| AI tools that hallucinate | LLM-generated answers often lack grounded citations |

---

## Core Value Proposition

ResearchPilot AI is differentiated by four properties that existing tools do not combine:

1. **Structured Decomposition** — Research questions are planned and decomposed before execution, not answered in a single LLM call.

2. **Multi-Source Parallel Research** — Web, academic, and private document sources are searched in parallel by specialized agents.

3. **Claim Verification** — A dedicated Critic Agent identifies unsupported claims and routes failed claims back through a controlled research loop.

4. **Citation-Backed Reports** — Every claim in the final report is traceable to a specific source with a proper citation.

No existing free-tier AI tool does all four. Most do one or two.

---

## Core Features

### P0 — Required for MVP

These features define the minimum viable ResearchPilot. Without any of these, the product is not functional.

| Feature | Description | Reason P0 |
|---------|-------------|-----------|
| **Research Question Input** | User submits a research question via UI | Core entry point |
| **Research Plan Generation** | Planner Agent decomposes the question into sub-questions | Required for structured research |
| **Web Research** | Web Research Agent uses Tavily to search and extract web sources | Primary research capability |
| **Evidence Extraction** | Agents extract relevant sentences/paragraphs from sources | Required for claim grounding |
| **Source Ranking** | Sources ranked by relevance and credibility | Prevents junk sources from corrupting output |
| **Claim Generation** | Evidence is mapped to claims | Required for verification step |
| **Critic Verification** | Critic Agent evaluates claim-evidence alignment | Core differentiator; prevents hallucinations |
| **Controlled Research Loop** | Failed claims trigger targeted additional research | Required for verification to be meaningful |
| **Report Synthesis** | Writer Agent generates structured report from verified findings | Core output |
| **Citation Mapping** | Every claim in the report is linked to a source | Core differentiator |
| **Research Status Streaming** | User sees real-time progress via SSE | Required for UX on long-running jobs |
| **Markdown Report Export** | User can export the report as Markdown | Minimum viable export |
| **Research History** | User can view previous research sessions | Required for basic usability |
| **Authentication** | Users must authenticate to use the system | Required to isolate user data |
| **Async Research Job Management** | Research runs as a background job; user can poll/stream status | Required for jobs that exceed HTTP timeout |

### P1 — Important After MVP

These features meaningfully extend the product but are not required to validate the core loop.

| Feature | Description | Reason P1 |
|---------|-------------|-----------|
| **Academic Research** | Semantic Scholar + arXiv agent for peer-reviewed sources | Valuable for academic users; builds on P0 web research |
| **Private Document RAG** | Upload documents and include them in research via Qdrant RAG | High value but operationally complex; depends on stable P0 |
| **PDF Export** | Generate a formatted PDF from the report | Requires additional tooling; not critical for validation |
| **Research Configuration** | Let users choose depth, source types, max iterations | Improves UX; not required for initial validation |
| **Agent Activity Transparency** | Show users which agents ran, what sources they found, what claims were rejected | High trust feature; requires clean logging first |
| **Citation Deduplication** | Merge identical sources cited multiple times | Quality improvement over P0 |
| **Contradiction Highlighting** | Explicitly surface contradictions in the report | Extends critic capability |

### P2 — Future / Advanced

These features represent a mature product and should not influence MVP architecture decisions.

| Feature | Description |
|---------|-------------|
| **Collaborative Research** | Multiple users working on shared research sessions |
| **Research Templates** | Pre-defined research workflows for common use cases |
| **Custom Agent Configuration** | Users define their own research pipelines |
| **Scheduled Research** | Recurring automated research on a topic |
| **API Access** | Programmatic access to ResearchPilot for integrations |
| **Multi-Modal Sources** | Research from images, videos, podcasts |
| **Fine-Tuned Critic Model** | Critic Agent fine-tuned on domain-specific claim verification |
| **Team Workspaces** | Organization-level accounts with shared documents |

---

## MVP Definition

The **Minimum Viable ResearchPilot** is a system that:

1. Accepts a research question from an authenticated user.
2. Decomposes it into sub-questions via a Planner Agent.
3. Executes web research in parallel using Tavily.
4. Extracts evidence from retrieved sources.
5. Ranks sources for credibility.
6. Maps evidence to claims.
7. Runs a Critic Agent to verify claim-evidence alignment.
8. Routes failed claims through a controlled research loop (max 2 retry iterations).
9. Generates a structured Markdown report with inline citations.
10. Streams research progress to the user via SSE.
11. Stores the research session and report in the database.
12. Allows the user to view and export the report as Markdown.

The MVP does **not** require: academic sources, private documents, PDF export, or advanced configuration.

---

## Non-Goals

The following will **NOT** be built in the initial implementation:

| Non-Goal | Reason |
|---------|--------|
| **Legal or medical advice** | Regulatory risk; out of scope for this product type |
| **Real-time collaborative editing** | Significant backend complexity; P2 |
| **Scheduling / recurring research** | Cron infrastructure not in scope for MVP |
| **Full-text search of research history** | Not required for MVP; P1/P2 |
| **Browser extension** | Out of scope |
| **Mobile native app** | Not in scope; responsive web is sufficient |
| **Social features (sharing, follows)** | Out of scope for initial product |
| **Custom LLM fine-tuning** | Requires ML infrastructure; far future |
| **Multi-tenancy / organization accounts** | P2 |
| **GDPR/CCPA compliance tooling** | Not in scope for initial version; must be added before public launch in regulated regions |

---

## Functional Requirements

### Research Lifecycle

| ID | Requirement |
|----|-------------|
| FR-01 | A user must be able to submit a research question of up to 1,000 characters. |
| FR-02 | The system must decompose the question into at least 2 and at most 8 sub-questions. |
| FR-03 | The system must execute research sub-tasks in parallel where possible. |
| FR-04 | Each sub-task must search at least one external source. |
| FR-05 | The system must extract verbatim evidence snippets from sources. |
| FR-06 | The system must assign a relevance score to each source. |
| FR-07 | The system must generate discrete, verifiable claims from evidence. |
| FR-08 | The Critic Agent must evaluate each claim against its evidence and assign a verification status. |
| FR-09 | Unverified claims must trigger a targeted retry research cycle up to a configurable maximum number of iterations. |
| FR-10 | The Writer Agent must produce a structured Markdown report with section headers and inline citation markers. |
| FR-11 | Every claim in the final report must reference at least one verified source. |

### User Interaction

| ID | Requirement |
|----|-------------|
| FR-12 | The user must see real-time progress updates during a research session. |
| FR-13 | The user must be able to cancel an in-progress research session. |
| FR-14 | The user must be able to view the full report on completion. |
| FR-15 | The user must be able to export the report as Markdown. |
| FR-16 | The user must be able to view their research history. |
| FR-17 | The user must be able to delete a research session and its associated data. |

### Authentication

| ID | Requirement |
|----|-------------|
| FR-18 | Users must authenticate before starting a research session. |
| FR-19 | Each user's research data must be isolated from other users. |
| FR-20 | The system must support email/password authentication at minimum. |

### Private Documents (P1)

| ID | Requirement |
|----|-------------|
| FR-21 | A user must be able to upload documents (PDF, TXT, DOCX) up to a configurable size limit. |
| FR-22 | Uploaded documents must be chunked and embedded into the user's private vector collection. |
| FR-23 | The RAG Agent must only retrieve from the uploading user's private collection. |

---

## Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Reliability** | The research pipeline must handle external API failures gracefully with retries and fallback. A single tool failure must not crash the entire research session. |
| **Latency** | A simple 3-5 sub-question research session should complete within 90 seconds under normal load. Verify this target against actual API latencies before committing. |
| **Security** | API keys must never be exposed to the frontend. User data must be isolated via Row-Level Security. All inputs must be validated and sanitized. |
| **Scalability** | The MVP design must not block future horizontal scaling. Async job processing must be decoupled from HTTP request threads. |
| **Observability** | All agent runs, tool calls, LLM calls, and errors must be traceable via Langfuse. Research sessions must have structured log output. |
| **Maintainability** | Each agent, tool, and LLM provider must be independently replaceable. No tight coupling between infrastructure layers. |
| **Accessibility** | The frontend must meet WCAG 2.1 AA minimum contrast requirements. All interactive elements must be keyboard navigable. |
| **Cost Control** | The system must enforce per-user and per-session token limits to prevent runaway LLM spend. Free-tier limits must be monitored. |

---

## Success Metrics

These metrics define what a successful ResearchPilot looks like. **Do not fabricate target values until baseline data is collected.**

| Metric | Definition | How Measured |
|--------|------------|--------------|
| **Research Completion Rate** | % of submitted research sessions that produce a final report | Sessions with `status = completed` / total sessions |
| **Claim Verification Rate** | % of generated claims that pass Critic verification on first pass | `claims.status = verified` / total claims |
| **Citation Coverage** | % of report claims that have at least one citation | Claims with ≥1 citation / total report claims |
| **Citation Source Quality** | % of cited sources with credibility score above threshold | TBD — define threshold after baseline |
| **Verification Loop Iterations** | Average number of critic retry cycles per research session | Stored per session in `critic_results` |
| **Research Latency (P50)** | Median time from research start to report completion | Measured per session |
| **Research Latency (P95)** | 95th percentile research completion time | Measured per session |
| **External API Failure Rate** | % of tool calls that fail after retries | Logged per agent_run |
| **LLM Fallback Rate** | % of LLM calls that fall through to a secondary provider | Logged via LLM router |
| **User Retention (D7)** | % of users who return within 7 days | TBD — requires user analytics |

---

## Risks

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **LLM Hallucination** | High | High | Critic Agent with evidence verification; structured prompts; citation requirement |
| **Unsupported Claims in Report** | Medium | High | Claims without evidence mapping are blocked from report by Writer Agent |
| **Infinite Agent Loops** | Medium | High | Hard cap on max_iterations per research session; session timeout enforced |
| **Search API Quota Exhaustion** | Medium | Medium | Per-session search budget; free-tier limits monitored; graceful degradation |
| **LLM Quota Exhaustion** | Medium | High | Provider fallback (Gemini → Groq → OpenRouter); per-session token budget |
| **Poor Source Quality** | High | Medium | Source credibility scoring; low-credibility sources flagged but not excluded |
| **Prompt Injection from Web Pages** | Medium | High | Evidence extraction sandboxed; no tool execution from web content; content sanitized before LLM |
| **Malicious Uploaded Documents** | Low (MVP: no upload) | High | P1 feature: scan uploads; reject executables; process in isolated context |
| **Excessive Token Consumption** | Medium | High | Per-session token budget enforced; truncation strategy for long sources |
| **SSRF via User-Provided URLs** | Low | High | URL allowlist for RAG; no direct user-URL fetching without validation |

### Product Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Users misinterpret AI-generated content as authoritative** | High | High | Disclaimers; verification status displayed prominently; citations shown |
| **Research sessions are too slow for casual users** | Medium | Medium | Progress streaming improves perceived performance; latency targets set |
| **Free-tier infrastructure cannot handle real load** | High | Medium | Explicitly documented; architecture designed for easy tier upgrade |
