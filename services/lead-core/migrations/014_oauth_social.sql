ALTER TABLE auth_challenges ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE auth_challenges ADD COLUMN IF NOT EXISTS state_hash TEXT;
ALTER TABLE auth_challenges ADD COLUMN IF NOT EXISTS pkce_verifier TEXT;
ALTER TABLE auth_challenges ADD COLUMN IF NOT EXISTS return_path TEXT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'auth_challenges'::regclass AND conname = 'auth_challenges_provider_check') THEN
        ALTER TABLE auth_challenges ADD CONSTRAINT auth_challenges_provider_check
            CHECK (provider IS NULL OR provider IN ('GOOGLE', 'GITHUB'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'auth_challenges'::regclass AND conname = 'auth_challenges_oauth_data_check') THEN
        ALTER TABLE auth_challenges ADD CONSTRAINT auth_challenges_oauth_data_check CHECK (
            purpose <> 'OAUTH_LOGIN' OR (
                provider IS NOT NULL AND btrim(provider) <> '' AND
                state_hash IS NOT NULL AND btrim(state_hash) <> '' AND
                pkce_verifier IS NOT NULL AND btrim(pkce_verifier) <> '' AND
                return_path IS NOT NULL AND btrim(return_path) <> '' AND
                return_path LIKE '/%' AND return_path NOT LIKE '//%' AND
                position('?' IN return_path) = 0 AND position('#' IN return_path) = 0 AND
                position(chr(92) IN return_path) = 0 AND return_path !~ '[[:cntrl:]]'
            )
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'auth_challenges'::regclass AND conname = 'auth_challenges_mfa_oauth_data_check') THEN
        ALTER TABLE auth_challenges ADD CONSTRAINT auth_challenges_mfa_oauth_data_check CHECK (
            purpose <> 'MFA_LOGIN' OR (
                provider IS NULL AND state_hash IS NULL AND pkce_verifier IS NULL AND return_path IS NULL
            )
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_auth_challenges_oauth_token_hash
    ON auth_challenges (token_hash) WHERE purpose = 'OAUTH_LOGIN';

CREATE TABLE IF NOT EXISTS social_identities (
    id UUID PRIMARY KEY,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('GOOGLE', 'GITHUB')),
    provider_subject TEXT NOT NULL CHECK (btrim(provider_subject) <> ''),
    email_at_link TEXT NOT NULL CHECK (btrim(email_at_link) <> ''),
    created_at TIMESTAMPTZ NOT NULL,
    last_login_at TIMESTAMPTZ NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'social_identities'::regclass AND conname = 'social_identities_provider_subject_key') THEN
        ALTER TABLE social_identities ADD CONSTRAINT social_identities_provider_subject_key
            UNIQUE (provider, provider_subject);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'social_identities'::regclass AND conname = 'social_identities_agent_provider_key') THEN
        ALTER TABLE social_identities ADD CONSTRAINT social_identities_agent_provider_key
            UNIQUE (agent_id, provider);
    END IF;
END $$;
