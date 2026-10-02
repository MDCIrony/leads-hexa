-- Per-key ordering of the relay: a row is only eligible while no older
-- unpublished row of its partition_key exists in the same channel, and this
-- index is what that anti-join probes.
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished_by_key
    ON outbox_events (channel, partition_key, occurred_on, id) WHERE published_at IS NULL;
