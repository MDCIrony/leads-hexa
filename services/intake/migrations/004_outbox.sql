-- Written in the same transaction as the job or record it describes (ADR-0025);
-- `id` is the event's own event_id, which consumers deduplicate on.
CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY,
    tenant_id UUID,
    partition_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    occurred_on TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    -- One relay per channel (ADR-0033/0034): `job` rides RabbitMQ, `internal` Kafka.
    channel TEXT NOT NULL CONSTRAINT outbox_events_channel_check CHECK (channel IN ('internal', 'job')),
    correlation_id TEXT
);

-- Partial: the relay only reads what has not gone out, a set that stays small.
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished_by_channel
    ON outbox_events (channel, attempts, occurred_on) WHERE published_at IS NULL;

-- Per-key ordering: a row is eligible only while no older unpublished row of
-- its partition_key exists in the channel, and this is what that anti-join probes.
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished_by_key
    ON outbox_events (channel, partition_key, occurred_on, id) WHERE published_at IS NULL;
