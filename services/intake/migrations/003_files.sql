-- The uploaded file itself is recorded before anything interprets it (ADR-0009, ADR-0034).
CREATE TABLE IF NOT EXISTS intake_files (
    job_id UUID PRIMARY KEY REFERENCES intake_jobs (id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    filename TEXT NOT NULL,
    content BYTEA NOT NULL,
    size_bytes INTEGER NOT NULL,
    parsed_at TIMESTAMPTZ
);
