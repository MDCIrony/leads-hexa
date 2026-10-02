-- Runs as the postgres superuser on every `docker compose up`, so every
-- statement is safe to repeat. psql does not interpolate variables inside
-- dollar-quoted DO blocks, hence \gexec over SELECTs that build the statements.
-- One role per extracted service, owning its database and its test database
-- and able to connect to nothing else (ADR-0031).

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', role, password)
FROM (VALUES ('notifications_svc', :'notifications_password'),
             ('identity_svc', :'identity_password')) AS roles (role, password)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role)
\gexec

-- Unconditional: keeps each role's password in step with Compose when it changes.
SELECT format('ALTER ROLE %I PASSWORD %L', role, password)
FROM (VALUES ('notifications_svc', :'notifications_password'),
             ('identity_svc', :'identity_password')) AS roles (role, password)
\gexec

-- The test databases exist up front because no service role has CREATEDB.
CREATE TEMP TABLE service_databases (name text, owner text);
INSERT INTO service_databases VALUES
    ('notifications_db', 'notifications_svc'), ('notifications_test', 'notifications_svc'),
    ('identity_db', 'identity_svc'), ('identity_test', 'identity_svc');

-- CREATE DATABASE cannot run in a transaction or a DO block; \gexec sends each statement on its own.
SELECT format('CREATE DATABASE %I OWNER %I', name, owner)
FROM service_databases
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = name)
\gexec

-- Unconditional: corrects a database that already existed under another owner.
SELECT format('ALTER DATABASE %I OWNER TO %I', name, owner) FROM service_databases
\gexec

SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', name) FROM service_databases
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', name, owner) FROM service_databases
\gexec

-- The monolith's databases too, so a service role reaches only its own. They
-- are created elsewhere (POSTGRES_DB, the test suite), hence only where they exist.
-- The backend connects as the postgres superuser, which this does not restrict.
SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', datname)
FROM pg_database WHERE datname IN ('leads_db', 'leads_test')
\gexec
