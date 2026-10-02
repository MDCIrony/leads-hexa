-- Where a lead came in from. tenant_id is a plain UUID: organizations live in
-- identity_db, so there is nothing here to reference.
CREATE TABLE IF NOT EXISTS lead_sources (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    -- The file-upload source stores its column mapping here.
    field_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Reserved for authenticating an external source by signature (webhooks).
    secret_hash TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    -- Two sources with the same name are indistinguishable to the manager.
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_lead_sources_tenant ON lead_sources (tenant_id);

-- Organizations whose default sources already exist: re-reading the compacted
-- tenants topic must not recreate a source the manager deleted afterwards.
CREATE TABLE IF NOT EXISTS provisioned_tenants (
    tenant_id UUID PRIMARY KEY,
    provisioned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
