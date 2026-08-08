CREATE TABLE IF NOT EXISTS sales_groups (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    default_strategy TEXT NOT NULL DEFAULT 'LOWEST_LOAD',
    capacity_per_agent INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    -- Two groups with the same name in one organization would be
    -- indistinguishable in the manager's interface.
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS assignment_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    min_score INTEGER NOT NULL DEFAULT 0,
    max_score INTEGER,
    -- SET NULL, not CASCADE: deleting a group must not silently delete the
    -- rules that pointed at it. The manager sees a rule without target and
    -- decides.
    target_group_id UUID REFERENCES sales_groups (id) ON DELETE SET NULL,
    target_agent_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    agent_match_mode TEXT NOT NULL DEFAULT 'ANY',
    strategy TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    rr_cursor INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_assignment_rules_tenant
    ON assignment_rules (tenant_id, priority DESC);

ALTER TABLE agents DROP COLUMN IF EXISTS team;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS group_id UUID
    REFERENCES sales_groups (id) ON DELETE SET NULL;
ALTER TABLE agents DROP COLUMN IF EXISTS active_leads_count;

CREATE INDEX IF NOT EXISTS idx_agents_group ON agents (group_id);

-- The engine asks for each agent's current load on every ingestion.
CREATE INDEX IF NOT EXISTS idx_leads_assigned_agent
    ON leads (assigned_agent_id) WHERE assigned_agent_id IS NOT NULL;

DROP TABLE IF EXISTS routing_rules;
