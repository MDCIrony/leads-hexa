-- One row per notice. The message is stored already composed rather than
-- rebuilt on read: rendering the bell must not need the lead of every notice,
-- and a deleted lead must not break the view.
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    recipient_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    lead_id UUID,
    intake_record_id UUID,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);

-- The bell asks exactly this: my unread ones, newest first.
CREATE INDEX IF NOT EXISTS idx_notifications_recipient
    ON notifications (recipient_id, is_read, created_at DESC);
