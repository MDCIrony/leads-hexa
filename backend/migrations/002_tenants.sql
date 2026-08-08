CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Every agent query now filters by organization.
CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents (tenant_id);

-- Without these, two accounts can share an email and login authenticates
-- against whichever row the database happens to return first.
CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_email_per_tenant
    ON agents (tenant_id, email) WHERE tenant_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_platform_admin_email
    ON agents (email) WHERE tenant_id IS NULL;
