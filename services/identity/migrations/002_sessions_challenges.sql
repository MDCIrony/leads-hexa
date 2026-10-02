CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    agent_id UUID NOT NULL REFERENCES agents (id),
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions (expires_at);

-- The constraints are declared inline, so CREATE TABLE IF NOT EXISTS already
-- makes a rerun a no-op; their names match the ones leads_db ended up with.
CREATE TABLE IF NOT EXISTS auth_challenges (
    token_hash TEXT PRIMARY KEY,
    -- Null for an OAuth login: nobody is known until the provider answers.
    agent_id UUID REFERENCES agents (id),
    purpose TEXT NOT NULL CONSTRAINT auth_challenges_purpose_check CHECK (btrim(purpose) <> ''),
    attempts INTEGER NOT NULL DEFAULT 0 CONSTRAINT auth_challenges_attempts_check CHECK (attempts >= 0),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    provider TEXT,
    state_hash TEXT,
    pkce_verifier TEXT,
    return_path TEXT,
    CONSTRAINT auth_challenges_provider_check
        CHECK (provider IS NULL OR provider IN ('GOOGLE', 'GITHUB')),
    -- Mirrors AuthChallenge's own validation, so a row written by hand cannot
    -- carry an open redirect the entity would have refused.
    CONSTRAINT auth_challenges_oauth_data_check CHECK (
        purpose <> 'OAUTH_LOGIN' OR (
            provider IS NOT NULL AND btrim(provider) <> '' AND
            state_hash IS NOT NULL AND btrim(state_hash) <> '' AND
            pkce_verifier IS NOT NULL AND btrim(pkce_verifier) <> '' AND
            return_path IS NOT NULL AND btrim(return_path) <> '' AND
            return_path LIKE '/%' AND return_path NOT LIKE '//%' AND
            position('?' IN return_path) = 0 AND position('#' IN return_path) = 0 AND
            position(chr(92) IN return_path) = 0 AND return_path !~ '[[:cntrl:]]'
        )
    ),
    CONSTRAINT auth_challenges_mfa_oauth_data_check CHECK (
        purpose <> 'MFA_LOGIN' OR (
            provider IS NULL AND state_hash IS NULL AND pkce_verifier IS NULL AND return_path IS NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_auth_challenges_expires_at ON auth_challenges (expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_challenges_oauth_token_hash
    ON auth_challenges (token_hash) WHERE purpose = 'OAUTH_LOGIN';
