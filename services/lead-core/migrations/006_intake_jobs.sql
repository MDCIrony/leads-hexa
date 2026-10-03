-- One row per ingestion operation, whatever its size. A single lead is a job of
-- one item: without that, the unit and the bulk paths need two different
-- contracts and the manager's inbox two ways of showing the same thing.
CREATE TABLE IF NOT EXISTS intake_jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES lead_sources (id),
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Null until the file is parsed: parsing happens in the background phase,
    -- after the response has already been sent.
    total_items INT,
    succeeded INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);

ALTER TABLE intake_records ADD COLUMN IF NOT EXISTS job_id UUID REFERENCES intake_jobs (id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_intake_records_job ON intake_records (job_id);
CREATE INDEX IF NOT EXISTS idx_intake_jobs_tenant_status ON intake_jobs (tenant_id, status);
