-- 001_initial_schema.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- TABLE DEFINITIONS
-- -----------------------------------------------------------------------------

CREATE TABLE public.users (
    id UUID PRIMARY KEY, -- Must match auth.users.id
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.research_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    research_question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    config JSONB DEFAULT '{}'::jsonb,
    iteration_count INT NOT NULL DEFAULT 0,
    total_claims INT,
    verified_claims INT,
    failure_reason TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE public.research_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL UNIQUE REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    sub_questions JSONB NOT NULL,
    sub_question_count INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.research_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    sub_question TEXT NOT NULL,
    research_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    iteration INT NOT NULL DEFAULT 1,
    failure_reason TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES public.research_tasks(id),
    url TEXT NOT NULL,
    title TEXT,
    source_type TEXT NOT NULL,
    relevance_score FLOAT,
    credibility_score FLOAT,
    domain TEXT,
    published_date TEXT,
    is_flagged BOOLEAN NOT NULL DEFAULT false,
    flag_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(session_id, url)
);

CREATE TABLE public.evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES public.research_tasks(id),
    content TEXT NOT NULL,
    sub_question TEXT NOT NULL,
    position_in_source INT,
    extraction_confidence FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    iteration INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.claim_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES public.claims(id) ON DELETE CASCADE,
    evidence_id UUID NOT NULL REFERENCES public.evidence(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(claim_id, evidence_id)
);

CREATE TABLE public.critic_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    claim_id UUID NOT NULL REFERENCES public.claims(id) ON DELETE CASCADE,
    verification_status TEXT NOT NULL,
    critic_notes TEXT,
    iteration INT NOT NULL,
    llm_provider_used TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL UNIQUE REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id),
    content_markdown TEXT NOT NULL,
    citation_map JSONB NOT NULL,
    total_citations INT NOT NULL,
    word_count INT,
    section_count INT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.research_sessions(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_summary JSONB,
    output_summary JSONB,
    error_message TEXT,
    llm_provider_used TEXT,
    tokens_used INT,
    duration_ms INT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    chunk_count INT,
    qdrant_collection_id TEXT,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);


-- -----------------------------------------------------------------------------
-- INDEXES
-- -----------------------------------------------------------------------------

CREATE INDEX idx_research_sessions_user_id ON public.research_sessions(user_id);
CREATE INDEX idx_research_sessions_user_id_status ON public.research_sessions(user_id, status);
CREATE INDEX idx_research_sessions_created_at_desc ON public.research_sessions(created_at DESC);

CREATE INDEX idx_research_tasks_session_id ON public.research_tasks(session_id);

CREATE INDEX idx_sources_session_id ON public.sources(session_id);

CREATE INDEX idx_evidence_session_id ON public.evidence(session_id);
CREATE INDEX idx_evidence_source_id ON public.evidence(source_id);

CREATE INDEX idx_claims_session_id ON public.claims(session_id);
CREATE INDEX idx_claims_session_id_status ON public.claims(session_id, status);

CREATE INDEX idx_claim_evidence_claim_id ON public.claim_evidence(claim_id);
CREATE INDEX idx_claim_evidence_evidence_id ON public.claim_evidence(evidence_id);

CREATE INDEX idx_critic_results_session_id ON public.critic_results(session_id);
CREATE INDEX idx_critic_results_claim_id ON public.critic_results(claim_id);

CREATE INDEX idx_reports_user_id ON public.reports(user_id);

CREATE INDEX idx_agent_runs_session_id ON public.agent_runs(session_id);

CREATE INDEX idx_user_documents_user_id ON public.user_documents(user_id);


-- -----------------------------------------------------------------------------
-- TRIGGERS (UPDATED_AT & AUTH.USERS SYNC)
-- -----------------------------------------------------------------------------

-- Trigger function for updated_at
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
CREATE TRIGGER update_research_sessions_updated_at BEFORE UPDATE ON public.research_sessions FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
CREATE TRIGGER update_claims_updated_at BEFORE UPDATE ON public.claims FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
CREATE TRIGGER update_reports_updated_at BEFORE UPDATE ON public.reports FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
CREATE TRIGGER update_user_documents_updated_at BEFORE UPDATE ON public.user_documents FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Trigger to sync auth.users into public.users
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, email, display_name)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'display_name');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- -----------------------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS)
-- -----------------------------------------------------------------------------

-- Enable RLS on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.critic_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_documents ENABLE ROW LEVEL SECURITY;

-- Note: The `service_role` key automatically bypasses RLS in Supabase,
-- so we do not need to create explicit policies for it, though we will
-- rely on it for all backend writes. 
-- We only need to define what the authenticated user (anon key with JWT) can do.

-- 1. users
CREATE POLICY "Users can view own profile" 
ON public.users FOR SELECT 
TO authenticated 
USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" 
ON public.users FOR UPDATE 
TO authenticated 
USING (auth.uid() = id);

-- 2. research_sessions
CREATE POLICY "Users can view own sessions" 
ON public.research_sessions FOR SELECT 
TO authenticated 
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions" 
ON public.research_sessions FOR INSERT 
TO authenticated 
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions" 
ON public.research_sessions FOR UPDATE 
TO authenticated 
USING (auth.uid() = user_id);

CREATE POLICY "Users can soft-delete own sessions" 
ON public.research_sessions FOR DELETE 
TO authenticated 
USING (auth.uid() = user_id);

-- 3. research_plans (Linked to session, frontend only reads)
CREATE POLICY "Users can view own plans via session" 
ON public.research_plans FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.research_sessions 
        WHERE id = public.research_plans.session_id 
        AND user_id = auth.uid()
    )
);

-- 4. research_tasks
CREATE POLICY "Users can view own tasks via session" 
ON public.research_tasks FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.research_sessions 
        WHERE id = public.research_tasks.session_id 
        AND user_id = auth.uid()
    )
);

-- 5. sources
CREATE POLICY "Users can view own sources via session" 
ON public.sources FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.research_sessions 
        WHERE id = public.sources.session_id 
        AND user_id = auth.uid()
    )
);

-- 6. evidence
CREATE POLICY "Users can view own evidence via session" 
ON public.evidence FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.research_sessions 
        WHERE id = public.evidence.session_id 
        AND user_id = auth.uid()
    )
);

-- 7. claims
CREATE POLICY "Users can view own claims via session" 
ON public.claims FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.research_sessions 
        WHERE id = public.claims.session_id 
        AND user_id = auth.uid()
    )
);

-- 8. claim_evidence
CREATE POLICY "Users can view own claim_evidence via claim" 
ON public.claim_evidence FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.claims c
        JOIN public.research_sessions rs ON c.session_id = rs.id
        WHERE c.id = public.claim_evidence.claim_id
        AND rs.user_id = auth.uid()
    )
);

-- 9. critic_results
CREATE POLICY "Users can view own critic_results via session" 
ON public.critic_results FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.research_sessions 
        WHERE id = public.critic_results.session_id 
        AND user_id = auth.uid()
    )
);

-- 10. reports (Denormalized with user_id for fast RLS)
CREATE POLICY "Users can view own reports" 
ON public.reports FOR SELECT 
TO authenticated 
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own reports" 
ON public.reports FOR DELETE 
TO authenticated 
USING (auth.uid() = user_id);

-- 11. agent_runs
CREATE POLICY "Users can view own agent_runs via session" 
ON public.agent_runs FOR SELECT 
TO authenticated 
USING (
    EXISTS (
        SELECT 1 FROM public.research_sessions 
        WHERE id = public.agent_runs.session_id 
        AND user_id = auth.uid()
    )
);

-- 12. user_documents
CREATE POLICY "Users can view own documents" 
ON public.user_documents FOR SELECT 
TO authenticated 
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own documents" 
ON public.user_documents FOR INSERT 
TO authenticated 
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own documents" 
ON public.user_documents FOR UPDATE 
TO authenticated 
USING (auth.uid() = user_id);

CREATE POLICY "Users can soft-delete own documents" 
ON public.user_documents FOR DELETE 
TO authenticated 
USING (auth.uid() = user_id);
