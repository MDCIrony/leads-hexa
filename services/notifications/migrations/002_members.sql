-- Local projection of the identity service's agents, rebuilt from its events.
-- `version` gates the upsert so a redelivered or reordered event cannot undo a later change.
CREATE TABLE IF NOT EXISTS members (
    agent_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    role TEXT NOT NULL,
    is_active BOOLEAN NOT NULL,
    version BIGINT NOT NULL
);

-- "Who are the active managers of this tenant" is the only question asked of it.
CREATE INDEX IF NOT EXISTS idx_members_tenant_role_active
    ON members (tenant_id, role) WHERE is_active;
