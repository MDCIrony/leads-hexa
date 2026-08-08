-- One column instead of a conditions table: a criterion is always read whole
-- with its rule and never queried on its own, so a join would buy nothing.
ALTER TABLE scoring_rules ADD COLUMN IF NOT EXISTS conditions JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE assignment_rules ADD COLUMN IF NOT EXISTS conditions JSONB NOT NULL DEFAULT '[]'::jsonb;

-- The reason travels as text, not as a rule id: deleting the rule must not
-- leave the lead unable to explain itself. Same call as ScoreBreakdown.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS disqualification_reason TEXT;

-- Guarded by the column's own existence rather than by a migration version:
-- test_migration_runner re-runs this whole file after the columns are gone.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scoring_rules' AND column_name = 'field'
    ) THEN
        UPDATE scoring_rules
        SET conditions = jsonb_build_array(
            jsonb_build_object('field', field, 'operator', operator, 'value', value)
        )
        WHERE conditions = '[]'::jsonb;
    END IF;
END $$;

ALTER TABLE scoring_rules DROP COLUMN IF EXISTS field;
ALTER TABLE scoring_rules DROP COLUMN IF EXISTS operator;
ALTER TABLE scoring_rules DROP COLUMN IF EXISTS value;

CREATE TABLE IF NOT EXISTS disqualification_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_disqualification_rules_tenant
    ON disqualification_rules (tenant_id, priority DESC);
