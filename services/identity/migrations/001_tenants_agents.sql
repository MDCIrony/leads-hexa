-- Final shape of leads_db's tenants and agents after backend migrations
-- 001..016, minus agents.group_id: sales groups belong to the leads side.
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    -- Bumped on every write: a projection applies a state only if it is newer.
    version BIGINT NOT NULL DEFAULT 1
);

-- tenant_id has no foreign key, as in leads_db: adding one is a schema
-- decision of its own, not part of moving the table.
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    role TEXT NOT NULL DEFAULT 'AGENT',
    hashed_password TEXT,
    tenant_id UUID,
    version BIGINT NOT NULL DEFAULT 1
);

-- Every agent query filters by organization.
CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents (tenant_id);

-- One account per address across the whole platform: login looks an agent up
-- by email alone, before it knows the organization.
CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_email_normalized ON agents (lower(email));
