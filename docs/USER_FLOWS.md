# USER_FLOWS.md — User Journey Document

> **Status:** Specification Frozen
> **Version:** 1.0.0
> **Last Updated:** 2026-09-16
> **Owner:** ResearchPilot AI Project

---

## Table of Contents

1. [First Visit (Unauthenticated)](#first-visit-unauthenticated)
2. [Signup Flow](#signup-flow)
3. [Login Flow](#login-flow)
4. [Core Research Flow](#core-research-flow)
5. [Research Failure Flows](#research-failure-flows)
6. [Private Document RAG Flow (P1)](#private-document-rag-flow-p1)
7. [Report Flow](#report-flow)
8. [Research History Flow](#research-history-flow)
9. [Account Management Flow](#account-management-flow)

---

## First Visit (Unauthenticated)

User arrives at the root URL without an active session.

```mermaid
flowchart TD
    A([User visits researchpilot.ai]) --> B{Authenticated?}
    B -- No --> C[Landing Page]
    B -- Yes --> D[Dashboard]

    C --> E[See product description and demo]
    E --> F{User action}
    F -- Clicks 'Start Researching' --> G[Signup Page]
    F -- Clicks 'Log In' --> H[Login Page]
    F -- Clicks 'Learn More' --> E

    G --> I[Signup Flow]
    H --> J[Login Flow]
```

### Landing Page Contents

- Product headline and one-line description
- Brief feature summary (3–4 key points)
- Call-to-action: "Start Researching" → Signup
- Secondary link: "Log In"
- No pricing; no marketing fluff

---

## Signup Flow

```mermaid
flowchart TD
    A([Signup Page]) --> B[Enter email + password]
    B --> C{Validate form}
    C -- Invalid --> D[Inline validation errors]
    D --> B
    C -- Valid --> E[POST to Supabase Auth]
    E --> F{Auth response}
    F -- Error: email exists --> G[Error: Account exists. Log in?]
    G --> H([Login Page])
    F -- Error: other --> I[Error message inline]
    I --> B
    F -- Success --> J[Confirmation email sent]
    J --> K[Email Confirmation Page]
    K --> L{User clicks confirm link}
    L -- Link valid --> M[Session created]
    M --> N([Dashboard])
    L -- Link expired --> O[Resend confirmation page]
    O --> J
```

### Notes

- Email confirmation is required before accessing the dashboard.
- Supabase Auth handles confirmation emails.
- No OAuth/social login in MVP. Add Google OAuth as a P1 enhancement.

---

## Login Flow

```mermaid
flowchart TD
    A([Login Page]) --> B[Enter email + password]
    B --> C{Validate form}
    C -- Invalid --> D[Inline error]
    D --> B
    C -- Valid --> E[POST to Supabase Auth]
    E --> F{Auth response}
    F -- Error: invalid credentials --> G[Error: Incorrect email or password]
    G --> B
    F -- Error: email not confirmed --> H[Error: Please confirm your email]
    H --> I[Resend confirmation link]
    F -- Success --> J[Session stored in HTTP-only cookie]
    J --> K{Was there a redirect destination?}
    K -- Yes --> L([Redirect to original destination])
    K -- No --> M([Dashboard])
```

---

## Core Research Flow

The primary user journey. This flow covers the entire research lifecycle from question submission to report.

```mermaid
flowchart TD
    A([Dashboard]) --> B[Research input form]
    B --> C[Enter research question]
    C --> D{Optional: configure research}
    D -- Configure --> E[Set max iterations, source types]
    E --> F[Submit]
    D -- Skip config --> F

    F --> G{Validate question}
    G -- Invalid: too short --> H[Inline error: question too short]
    H --> C
    G -- Invalid: too long --> I[Inline error: question too long]
    I --> C
    G -- Valid --> J[POST /api/v1/research]

    J --> K{API response}
    K -- 409: Max sessions reached --> L[Error: 3 sessions already active. Cancel one to start a new research.]
    L --> A
    K -- 429: Rate limited --> M[Error: Rate limit reached. Try again in X minutes.]
    M --> A
    K -- 202 Accepted --> N[Navigate to Research Progress Page]

    N --> O[Connect to SSE stream]
    O --> P[Display: Planning phase]
    P --> Q[Display: Research phase - parallel tasks]
    Q --> R[Display: Evidence extraction]
    R --> S[Display: Verification phase]
    S --> T{Unverified claims?}
    T -- Yes AND iterations < max --> U[Display: Retry phase]
    U --> Q
    T -- No OR max reached --> V[Display: Writing phase]
    V --> W[Display: Research complete]
    W --> X[Navigate to Report Page]
```

### Research Progress Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  Your Research                               [Cancel ×] │
│  "What are the main mechanisms by which..."             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ◉ Searching sources            [02:14 elapsed]         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 60%                    │
│                                                         │
│  Research Tasks:                                        │
│  ✓ Attention-based failure modes        5 sources       │
│  ◐ Chain-of-thought limitations         Searching...   │
│  ○ Prompting failure patterns           Queued          │
│  ○ Benchmark saturation                 Queued          │
│                                                         │
│  Agent Activity:                                        │
│  ✓ Planner Agent      Completed    0.8s                 │
│  ◐ Web Research Agent Running     02:14s                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Research Failure Flows

### Flow A: Search API Fails

```mermaid
flowchart TD
    A([Research running]) --> B[Tavily API fails for a sub-task]
    B --> C{Other tasks running?}
    C -- Yes --> D[Log failure; continue with other tasks]
    D --> E[Research continues with partial results]
    E --> F[Report includes note: some sources unavailable]
    C -- No: all tasks failed --> G[Session status: failed]
    G --> H[SSE event: error]
    H --> I[User sees: Research could not complete - no sources retrieved]
    I --> J[Option: Retry]
    J --> K([New research session])
```

### Flow B: LLM Provider Fails

```mermaid
flowchart TD
    A([Agent running]) --> B[Gemini API fails - rate limit or error]
    B --> C[LLMRouter tries Groq]
    C --> D{Groq succeeds?}
    D -- Yes --> E[Agent continues with Groq]
    E --> F([Normal research flow continues])
    D -- No --> G[LLMRouter tries OpenRouter]
    G --> H{OpenRouter succeeds?}
    H -- Yes --> I[Agent continues with OpenRouter]
    I --> F
    H -- No --> J[ProviderExhaustedError raised]
    J --> K[Session status: failed]
    K --> L[SSE event: error - all LLM providers unavailable]
    L --> M[User sees error with retry option]
```

### Flow C: Verification Fails to Resolve

```mermaid
flowchart TD
    A([Verification loop]) --> B[Iteration 1: 3 claims unverified]
    B --> C[Targeted retry research]
    C --> D[Iteration 2: 1 claim still unverified]
    D --> E{iterations >= max_iterations?}
    E -- Yes --> F[Max iterations reached]
    F --> G[Unverified claims excluded from report]
    G --> H[Writer Agent proceeds with verified claims only]
    H --> I[Report includes note: 1 claim could not be verified and was excluded]
    I --> J([Report page - with exclusion warning])
    E -- No --> C
```

### Flow D: Research Timeout

```mermaid
flowchart TD
    A([Research running]) --> B[300 seconds elapsed]
    B --> C[Session timeout triggered]
    C --> D[Session status: failed]
    D --> E[SSE event: error - research timed out]
    E --> F[User sees: Research took too long. The topic may be too broad.]
    F --> G[Option: Start new research with narrower question]
```

### Flow E: User Cancels Research

```mermaid
flowchart TD
    A([Research progress page]) --> B[User clicks Cancel]
    B --> C[Confirm dialog: Cancel this research?]
    C --> D{User confirms?}
    D -- No --> A
    D -- Yes --> E[DELETE /api/v1/research/{id}]
    E --> F[Session status: cancelled]
    F --> G[SSE connection closed]
    G --> H([Dashboard - session shows as cancelled])
```

---

## Private Document RAG Flow (P1)

> This flow is a P1 feature. Not implemented in MVP.

```mermaid
flowchart TD
    A([Documents Page]) --> B[Click: Upload Document]
    B --> C[File picker / drag-and-drop]
    C --> D{File validation}
    D -- Invalid type --> E[Error: Only PDF, TXT, DOCX supported]
    E --> C
    D -- Too large --> F[Error: File exceeds 10MB limit]
    F --> C
    D -- Valid --> G[POST /api/v1/documents multipart]
    G --> H[Document record created: status=processing]
    H --> I[Display: Processing document...]
    I --> J[Backend: chunk document]
    J --> K[Backend: embed chunks via LLM embedding model]
    K --> L[Backend: store vectors in user's Qdrant collection]
    L --> M[Document status: completed]
    M --> N[Display: Document ready for research]

    N --> O{User starts research?}
    O -- Yes --> P[Research config: include private documents]
    P --> Q[RAG Agent queries user's Qdrant collection]
    Q --> R[Evidence retrieved from private document]
    R --> S([Normal research flow continues])
```

### RAG Research Sub-Flow

```mermaid
flowchart TD
    A([Research task: rag type]) --> B[PrivateRAGAgent activated]
    B --> C[Embed sub-question using embedding model]
    C --> D[Query user's Qdrant collection - user_id namespace]
    D --> E{Results found?}
    E -- No results --> F[Return empty ResearchResult]
    F --> G[Note: no private document evidence for this sub-question]
    E -- Yes --> H[Return matched chunks as evidence]
    H --> I([Evidence Extractor processes results])
```

---

## Report Flow

```mermaid
flowchart TD
    A([SSE: event done]) --> B[Navigate to Report Page]
    B --> C[GET /api/v1/research/{id}/report]
    C --> D[Render structured report]

    D --> E[Report sections visible]
    E --> F{User explores report}

    F -- Clicks citation [n] --> G[Highlight source in reference list]
    G --> H[Tooltip: source title, URL, type]

    F -- Clicks source URL --> I[Open source in new tab]

    F -- Clicks 'View Sources' tab --> J[Source list panel]
    J --> K[Show all sources with credibility + relevance scores]
    K --> L{Source is flagged?}
    L -- Yes --> M[Show flag warning: low credibility]
    L -- No --> N[Normal display]

    F -- Clicks 'Export Markdown' --> O[GET /api/v1/research/{id}/report?format=markdown]
    O --> P[Browser downloads report.md file]

    F -- Clicks 'View Claims' tab --> Q[Claim list with verification status]
    Q --> R[Each claim shows: content, status badge, evidence count]
    R --> S{Excluded claims shown?}
    S -- Yes --> T[Shown with 'Excluded' badge and reason]
```

### Report Page Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to History            [Export Markdown] [PDF (P1)] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Research Report                           [Summary Stats] │
│  "What are the main mechanisms..."         10 claims ✓      │
│  Completed: Sep 16, 2026 · 1m 23s         8 sources cited  │
│                                                             │
│  [Report] [Sources] [Claims] [Agent Log]                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ## Introduction                                            │
│  Large language models frequently fail at multi-step        │
│  reasoning tasks [1][2] due to...                           │
│                                                             │
│  ## Attention-Based Failures                                │
│  ...                                                        │
│                                                             │
│  ## References                                              │
│  [1] Author et al. (2024). Title. URL                       │
│  [2] Domain.com. Title. URL                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Research History Flow

```mermaid
flowchart TD
    A([Dashboard]) --> B[Research history list]
    B --> C{List is empty?}
    C -- Yes --> D[Empty state: Start your first research]
    D --> E[Click: Start Research]
    E --> F([Research input form])
    C -- No --> G[Show sessions: question, status, date, stats]

    G --> H{User action}
    H -- Clicks completed session --> I[Navigate to Report Page]
    H -- Clicks in-progress session --> J[Navigate to Research Progress Page]
    H -- Clicks failed session --> K[Session detail: failure reason + Retry option]
    H -- Clicks delete icon --> L[Confirm: Delete this research?]
    L --> M{Confirmed?}
    M -- No --> G
    M -- Yes --> N[DELETE /api/v1/research/{id}]
    N --> O[Session removed from list]

    G --> P{User filters?}
    P -- Filter by status --> Q[GET /api/v1/research?status=completed]
    Q --> G
    P -- Load more --> R[GET /api/v1/research?page=2]
    R --> G
```

---

## Account Management Flow

```mermaid
flowchart TD
    A([User menu in nav]) --> B{User action}
    B -- Profile --> C[Profile page]
    B -- Log Out --> D[Supabase Auth signOut]
    D --> E([Landing Page])

    C --> F[View: email, display name]
    F --> G{User edits?}
    G -- Edit display name --> H[PATCH /api/v1/users/me]
    H --> I{Success?}
    I -- Yes --> J[Profile updated]
    I -- No --> K[Error message]
    K --> F

    G -- Change password --> L[Supabase Auth: password reset email]
    L --> M[Check email for reset link]
```
