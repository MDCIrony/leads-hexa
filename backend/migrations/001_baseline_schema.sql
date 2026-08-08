CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT NOT NULL,
    -- NUMERIC, not DOUBLE PRECISION: a budget is money, and binary floating
    -- point cannot represent it exactly.
    budget NUMERIC(14, 2) NOT NULL,
    industry TEXT NOT NULL,
    custom_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    phone TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    assigned_agent_id UUID,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    field TEXT NOT NULL,
    operator TEXT NOT NULL,
    -- JSONB, like custom_attributes: the value a rule compares against is a
    -- scalar whose type is decided per row, and encoding JSON into TEXT would
    -- hide that from the database.
    value JSONB NOT NULL,
    score_delta INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS routing_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    min_score INTEGER NOT NULL,
    target_team TEXT NOT NULL,
    assignment_strategy TEXT NOT NULL,
    target_agent_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    team TEXT NOT NULL,
    active_leads_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    role TEXT NOT NULL DEFAULT 'AGENT',
    hashed_password TEXT,
    tenant_id UUID
);

CREATE TABLE IF NOT EXISTS webhook_configs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    target_url TEXT NOT NULL,
    secret_token TEXT NOT NULL
);
