-- Where a lead came in from. Without it, "where do my leads come from?" has
-- no answer, and F2c has nothing to condition a per-channel routing rule on.
CREATE TABLE IF NOT EXISTS lead_sources (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    -- The file-upload source stores its column mapping here, so the machinery
    -- pays for itself from day one instead of being scaffolding for F3b.
    field_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- F3b authenticates an external source by signature. The column exists now
    -- so webhooks will not need a migration of their own.
    secret_hash TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    -- Two sources with the same name are indistinguishable to the manager.
    UNIQUE (tenant_id, name)
);

-- Every payload that arrives is persisted before anyone tries to interpret it.
-- What cannot be interpreted stays here instead of vanishing, which is what
-- lets a manager answer "how many leads am I losing?".
CREATE TABLE IF NOT EXISTS intake_records (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES lead_sources (id),
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    -- Set once the record is promoted. SET NULL, not CASCADE: deleting a lead
    -- must not erase the evidence that it once arrived.
    lead_id UUID REFERENCES leads (id) ON DELETE SET NULL,
    received_at TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ
);

-- Per-field detail of why a record could not be interpreted: what field, what
-- arrived, what failed. A single message would not let the manager fix a CSV
-- column mapping.
CREATE TABLE IF NOT EXISTS intake_errors (
    id UUID PRIMARY KEY,
    intake_record_id UUID NOT NULL REFERENCES intake_records (id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    received_value TEXT,
    message TEXT NOT NULL,
    error_code TEXT
);

-- A lead always came in from somewhere.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_id UUID NOT NULL REFERENCES lead_sources (id);

-- The baseline left leads.tenant_id without a foreign key. A lead pointing at
-- an organization that does not exist is a row no tenant-filtered query ever
-- returns: invisible to every manager, and impossible to delete through the
-- application. Closed here because this migration already rewrites the same
-- tests the constraint affects.
-- PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS, and test_migration_runner.py
-- re-applies every file against a schema that already has it (tracking table
-- reset, tables intact), so the guard is done by hand via pg_constraint.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_leads_tenant'
    ) THEN
        ALTER TABLE leads ADD CONSTRAINT fk_leads_tenant
            FOREIGN KEY (tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;
    END IF;
END $$;

-- Contactability is an organization's rule, not an invariant of the data: a
-- lead with no email must be able to exist and be disqualified by a rule
-- (F2c), not be destroyed on arrival. See docs/product/03.
ALTER TABLE leads ALTER COLUMN email DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lead_sources_tenant ON lead_sources (tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads (tenant_id, source_id);
-- The inbox lists what needs the manager's attention, newest first.
CREATE INDEX IF NOT EXISTS idx_intake_records_inbox
    ON intake_records (tenant_id, status, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_intake_errors_record ON intake_errors (intake_record_id);
