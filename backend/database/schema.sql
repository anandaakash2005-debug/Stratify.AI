-- ============================================================
-- database/schema.sql
-- Run this once in Supabase SQL editor to bootstrap all tables.
-- ============================================================

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    full_name   TEXT,
    role        TEXT DEFAULT 'founder',        -- founder | mentor | investor | admin
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Startups ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS startups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    name            TEXT,
    idea            TEXT NOT NULL,
    market          TEXT NOT NULL,
    business_model  TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    stage           TEXT DEFAULT 'idea',       -- idea | mvp | growth | scale
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Reports ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id      UUID REFERENCES startups(id) ON DELETE CASCADE,

    share_id        TEXT UNIQUE,

    report_type     TEXT DEFAULT 'full',

    raw_ai_response JSONB,

    swot            JSONB,
    risks           JSONB,
    competitors     JSONB,
    recommendations JSONB,
    gtm_suggestions JSONB,

    model_used      TEXT,
    tokens_used     INT,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Scores ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scores (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id           UUID REFERENCES startups(id) ON DELETE CASCADE,
    report_id            UUID REFERENCES reports(id) ON DELETE CASCADE,
    health_score         NUMERIC(5,2),          -- 0–100
    risk_level           TEXT,                  -- Low | Medium | High | Critical
    survival_probability TEXT,                  -- e.g. "68%"
    pmf_score            NUMERIC(5,2),
    competition_score    NUMERIC(5,2),
    monetization_score   NUMERIC(5,2),
    team_score           NUMERIC(5,2),
    market_score         NUMERIC(5,2),
    scoring_version      TEXT DEFAULT 'v1',     -- bump when algorithm changes
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_startups_user_id   ON startups(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_startup_id ON reports(startup_id);
CREATE INDEX IF NOT EXISTS idx_scores_startup_id  ON scores(startup_id);

-- ── Row-level security (enable in Supabase dashboard + add policies) ──────────
ALTER TABLE users    ENABLE ROW LEVEL SECURITY;
ALTER TABLE startups ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports  ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores   ENABLE ROW LEVEL SECURITY;

-- After bootstrap, apply database/analysis_pipeline.sql for atomic analysis persistence and ownership policies.
