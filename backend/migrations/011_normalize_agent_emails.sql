BEGIN;

LOCK TABLE agents IN ACCESS EXCLUSIVE MODE;

DO $$
DECLARE
    duplicate_email TEXT;
BEGIN
    SELECT lower(btrim(email))
    INTO duplicate_email
    FROM agents
    GROUP BY lower(btrim(email))
    HAVING COUNT(*) > 1
    LIMIT 1;

    IF duplicate_email IS NOT NULL THEN
        RAISE EXCEPTION 'Cannot normalize agent emails: duplicate normalized email "%"', duplicate_email;
    END IF;
END $$;

UPDATE agents SET email = lower(btrim(email)) WHERE email <> lower(btrim(email));

CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_email_normalized ON agents (lower(email));
DROP INDEX IF EXISTS idx_agents_email_per_tenant;
DROP INDEX IF EXISTS idx_agents_platform_admin_email;

COMMIT;
