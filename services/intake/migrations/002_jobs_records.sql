-- One row per ingestion operation, whatever its size. A single lead is a job of
-- one item, so the unit and bulk paths share one contract.
CREATE TABLE IF NOT EXISTS intake_jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    source_id UUID NOT NULL REFERENCES lead_sources (id),
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Null until the file is parsed: parsing happens after the response is sent.
    total_items INT,
    succeeded INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    correlation_id TEXT
);

-- Every payload that arrives is persisted before anyone tries to interpret it.
CREATE TABLE IF NOT EXISTS intake_records (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    source_id UUID NOT NULL REFERENCES lead_sources (id),
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    -- The lead lives in leads_db: an external id, not a foreign key.
    lead_id UUID,
    received_at TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ,
    job_id UUID REFERENCES intake_jobs (id) ON DELETE CASCADE
);

-- Per-field detail of why a record could not be interpreted, so a manager can
-- fix a CSV column mapping instead of reading one opaque message.
CREATE TABLE IF NOT EXISTS intake_errors (
    id UUID PRIMARY KEY,
    intake_record_id UUID NOT NULL REFERENCES intake_records (id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    received_value TEXT,
    message TEXT NOT NULL,
    error_code TEXT
);

-- The inbox lists what needs the manager's attention, newest first.
CREATE INDEX IF NOT EXISTS idx_intake_records_inbox
    ON intake_records (tenant_id, status, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_intake_records_job ON intake_records (job_id);
CREATE INDEX IF NOT EXISTS idx_intake_errors_record ON intake_errors (intake_record_id);
CREATE INDEX IF NOT EXISTS idx_intake_jobs_tenant_status ON intake_jobs (tenant_id, status);
