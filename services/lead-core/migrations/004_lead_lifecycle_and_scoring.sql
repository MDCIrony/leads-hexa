ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS discard_reason TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
-- The breakdown is stored, not recomputed: the rules that produced a score
-- can be edited or deleted afterwards, and the lead must still explain itself.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_breakdown JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- The agent's own dashboard lists their leads newest first.
CREATE INDEX IF NOT EXISTS idx_leads_agent_recent
    ON leads (tenant_id, assigned_agent_id, created_at DESC)
    WHERE assigned_agent_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_leads_tenant_status ON leads (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_scoring_rules_tenant ON scoring_rules (tenant_id, priority DESC);
