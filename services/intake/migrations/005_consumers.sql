-- Written in the same transaction as the consumer's effect: a redelivered
-- event finds its row and does nothing.
CREATE TABLE IF NOT EXISTS processed_events (
    consumer TEXT NOT NULL,
    event_id UUID NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, event_id)
);
