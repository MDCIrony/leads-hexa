-- lead-core's copy of the agents it routes to. Identity columns are written
-- only by the consumer of internal.identity.agents, gated on version;
-- group_id belongs to lead-core and no identity event touches it.
CREATE TABLE IF NOT EXISTS advisors (
    agent_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active BOOLEAN NOT NULL,
    version BIGINT NOT NULL,
    group_id UUID NULL REFERENCES sales_groups (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_advisors_tenant_group ON advisors (tenant_id, group_id);
CREATE INDEX IF NOT EXISTS idx_advisors_tenant_active ON advisors (tenant_id) WHERE is_active;

-- Seeded from the monolith's own table so routing keeps its candidates before
-- the first event arrives. The platform admin has no organization to route in.
INSERT INTO advisors (agent_id, tenant_id, name, role, is_active, version, group_id)
SELECT id, tenant_id, name, role, is_active, version, group_id
FROM agents
WHERE tenant_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Organizations whose default sources already exist: re-reading the compacted
-- tenants topic must not recreate a source the manager deleted afterwards.
CREATE TABLE IF NOT EXISTS provisioned_tenants (
    tenant_id UUID PRIMARY KEY,
    provisioned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO provisioned_tenants (tenant_id)
SELECT id FROM tenants
ON CONFLICT DO NOTHING;

-- After the cut new organizations are born in identity_db, and a source or a
-- group of theirs would violate a foreign key to this frozen table. Looked up
-- by target rather than by name: several were declared inline, auto-named.
DO $$
DECLARE
    fk record;
BEGIN
    FOR fk IN
        SELECT conrelid::regclass AS table_name, conname
        FROM pg_constraint
        WHERE contype = 'f' AND confrelid = 'tenants'::regclass
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', fk.table_name, fk.conname);
    END LOOP;
END $$;
