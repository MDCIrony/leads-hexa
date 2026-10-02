-- Runs as the postgres superuser on every `docker compose up`, so every
-- statement is safe to repeat. psql does not interpolate variables inside
-- dollar-quoted DO blocks, hence \gexec over SELECTs that build the statements.

SELECT format('CREATE ROLE notifications_svc LOGIN PASSWORD %L', :'notifications_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'notifications_svc')
\gexec

-- Unconditional: keeps the role's password in step with Compose when it changes.
SELECT format('ALTER ROLE notifications_svc PASSWORD %L', :'notifications_password')
\gexec

-- CREATE DATABASE cannot run in a transaction or a DO block; \gexec sends each statement on its own.
SELECT format('CREATE DATABASE %I OWNER notifications_svc', name)
FROM (VALUES ('notifications_db'), ('notifications_test')) AS databases (name)
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = name)
\gexec

SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', name)
FROM (VALUES ('notifications_db'), ('notifications_test')) AS databases (name)
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO notifications_svc', name)
FROM (VALUES ('notifications_db'), ('notifications_test')) AS databases (name)
\gexec
