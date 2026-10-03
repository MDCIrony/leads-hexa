-- Supports GET /leads?updated_since=, the replay a consumer uses to catch up
-- on what changed while it was away. Without it that filter is a sequential
-- scan of the whole organization.
CREATE INDEX IF NOT EXISTS idx_leads_tenant_updated
    ON leads (tenant_id, updated_at);
