-- Admission is idempotent by (tenant_id, intake_record_id) (ADR-0035): the
-- lead remembers the intake record it came from, so a redelivered or raced
-- admission finds it instead of building a second lead. After the cut the
-- record lives in intake_db, so this is a plain column, not a foreign key.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS intake_record_id UUID;

-- Leads promoted before this migration carry the link on the record side only.
UPDATE leads l
SET intake_record_id = r.id
FROM intake_records r
WHERE r.lead_id = l.id AND l.intake_record_id IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_leads_tenant_intake_record') THEN
        ALTER TABLE leads
            ADD CONSTRAINT uq_leads_tenant_intake_record UNIQUE (tenant_id, intake_record_id);
    END IF;
END $$;

-- After the cut new sources are born in intake_db, and a lead admitted from
-- one would violate a foreign key to this frozen table. Looked up by target
-- rather than by name, as in 017: it was declared inline, auto-named.
DO $$
DECLARE
    fk record;
BEGIN
    FOR fk IN
        SELECT conname
        FROM pg_constraint
        WHERE contype = 'f' AND conrelid = 'leads'::regclass AND confrelid = 'lead_sources'::regclass
    LOOP
        EXECUTE format('ALTER TABLE leads DROP CONSTRAINT %I', fk.conname);
    END LOOP;
END $$;
