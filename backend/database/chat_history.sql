-- ============================================================
-- Satquery.AI chat_history table migration
-- Creates the chat_history table for AI mentor conversation persistence
-- Safe to rerun: uses IF NOT EXISTS and replaces the named RLS policies atomically
-- Apply in Supabase: Dashboard -> SQL Editor -> New query -> paste -> Review -> Run
-- ============================================================

BEGIN;

-- ── Create chat_history table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chat_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    message         TEXT NOT NULL,
    response        TEXT NOT NULL,
    intent          TEXT,
    confidence      NUMERIC,
    report_id       UUID REFERENCES public.reports(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Add indexes for performance ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_chat_history_user_id_created_at 
    ON public.chat_history(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_history_report_id 
    ON public.chat_history(report_id);

-- ── Enable Row Level Security ────────────────────────────────────────────────
ALTER TABLE public.chat_history ENABLE ROW LEVEL SECURITY;

-- ── RLS Policies ─────────────────────────────────────────────────────────────
-- Authenticated users can read their own chat history
DROP POLICY IF EXISTS chat_history_user_read ON public.chat_history;
CREATE POLICY chat_history_user_read 
    ON public.chat_history 
    FOR SELECT 
    TO authenticated 
    USING (user_id = auth.uid());

-- Authenticated users can insert their own chat history
DROP POLICY IF EXISTS chat_history_user_insert ON public.chat_history;
CREATE POLICY chat_history_user_insert 
    ON public.chat_history 
    FOR INSERT 
    TO authenticated 
    WITH CHECK (user_id = auth.uid());

-- Service role can manage all chat history (for backend operations)
GRANT ALL ON public.chat_history TO service_role;

-- Authenticated users can read/write their own
GRANT SELECT, INSERT ON public.chat_history TO authenticated;

COMMIT;

-- Verification query (run separately to check):
-- SELECT COUNT(*) FROM public.chat_history;
-- SELECT * FROM public.chat_history LIMIT 5;
