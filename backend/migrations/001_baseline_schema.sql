CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT NOT NULL,
    budget DOUBLE PRECISION NOT NULL,
    industry TEXT NOT NULL,
    custom_attributes TEXT,
    phone TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    assigned_agent_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_rules (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    field TEXT NOT NULL,
    operator TEXT NOT NULL,
    value TEXT NOT NULL,
    score_delta INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS routing_rules (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    min_score INTEGER NOT NULL,
    target_team TEXT NOT NULL,
    assignment_strategy TEXT NOT NULL,
    target_agent_ids TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    team TEXT NOT NULL,
    active_leads_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    role TEXT NOT NULL DEFAULT 'AGENT',
    hashed_password TEXT,
    tenant_id TEXT
);

CREATE TABLE IF NOT EXISTS webhook_configs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    target_url TEXT NOT NULL,
    secret_token TEXT NOT NULL
);
