-- The transactional half of at-least-once delivery (ADR-0025): a row here is
-- written inside the same transaction as the lead it describes, so a
-- rollback takes both or neither. `id` is the event's own event_id, not a
-- fresh one — a consumer uses it to deduplicate.
CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    partition_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    occurred_on TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);

-- Partial: the relay only ever reads what has not gone out, and that set stays
-- small even when the table does not.
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished
    ON outbox_events (occurred_on) WHERE published_at IS NULL;
