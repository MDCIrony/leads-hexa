-- Contract step of the decoupling (F5): these tables were copied to
-- identity_db, notifications_db and intake_db in F2-F4, and nothing in
-- lead-core reads or writes them since. processed_events goes too: the only
-- consumer left here is idempotent by version and never used it.
-- Names resolve through to_regclass, so the search_path decides the schema.
DO $$
DECLARE
    leaving regclass[];
    fk record;
BEGIN
    SELECT coalesce(array_agg(to_regclass(name)) FILTER (WHERE to_regclass(name) IS NOT NULL), '{}')
    INTO leaving
    FROM unnest(ARRAY[
        'tenants', 'agents', 'auth_sessions', 'auth_challenges', 'agent_mfa',
        'mfa_recovery_codes', 'social_identities', 'notifications', 'lead_sources',
        'intake_jobs', 'intake_records', 'intake_errors', 'intake_files',
        'provisioned_tenants', 'processed_events'
    ]) AS name;

    -- 017 and 018 already removed every key from a staying table into these;
    -- this covers a volume where they were never removed.
    FOR fk IN
        SELECT conrelid::regclass AS table_name, conname
        FROM pg_constraint
        WHERE contype = 'f' AND confrelid = ANY (leaving) AND NOT conrelid = ANY (leaving)
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', fk.table_name, fk.conname);
    END LOOP;

    -- No CASCADE on purpose: keys among the leaving tables go with them, and
    -- any other dependency (a view, a key nobody expected) must fail the
    -- migration instead of disappearing silently.
    IF cardinality(leaving) > 0 THEN
        EXECUTE 'DROP TABLE IF EXISTS ' || array_to_string(leaving::text[], ', ');
    END IF;
END $$;
