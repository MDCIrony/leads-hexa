CREATE TABLE IF NOT EXISTS social_identities (
    id UUID PRIMARY KEY,
    agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('GOOGLE', 'GITHUB')),
    provider_subject TEXT NOT NULL CHECK (btrim(provider_subject) <> ''),
    email_at_link TEXT NOT NULL CHECK (btrim(email_at_link) <> ''),
    created_at TIMESTAMPTZ NOT NULL,
    last_login_at TIMESTAMPTZ NOT NULL,
    -- One provider account opens one agent, and an agent links each provider once.
    CONSTRAINT social_identities_provider_subject_key UNIQUE (provider, provider_subject),
    CONSTRAINT social_identities_agent_provider_key UNIQUE (agent_id, provider)
);
