-- One relay per channel (ADR-0033/0034): a webhook that is down must stop
-- holding back internal events and queued jobs.
ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'product';
ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS correlation_id TEXT;
-- Identity state of the platform admin has no tenant.
ALTER TABLE outbox_events ALTER COLUMN tenant_id DROP NOT NULL;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'outbox_events_channel_check') THEN
        ALTER TABLE outbox_events ADD CONSTRAINT outbox_events_channel_check
            CHECK (channel IN ('product', 'internal', 'job'));
    END IF;
END $$;
DROP INDEX IF EXISTS idx_outbox_unpublished;
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished_by_channel
    ON outbox_events (channel, attempts, occurred_on) WHERE published_at IS NULL;

-- Written in the same transaction as the consumer's effect: a redelivered
-- event finds its row and does nothing.
CREATE TABLE IF NOT EXISTS processed_events (
    consumer TEXT NOT NULL,
    event_id UUID NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, event_id)
);

-- The uploaded file itself is recorded before anything interprets it (ADR-0009, ADR-0034).
CREATE TABLE IF NOT EXISTS intake_files (
    job_id UUID PRIMARY KEY REFERENCES intake_jobs(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    filename TEXT NOT NULL,
    content BYTEA NOT NULL,
    size_bytes INTEGER NOT NULL,
    parsed_at TIMESTAMPTZ
);

ALTER TABLE intake_jobs ADD COLUMN IF NOT EXISTS correlation_id TEXT;

-- Bumped on every write: a projection applies a state only if it is newer.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 1;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 1;
