CREATE TABLE IF NOT EXISTS agent_mfa (
    agent_id UUID PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
    secret_ciphertext TEXT NOT NULL CHECK (btrim(secret_ciphertext) <> ''),
    enabled_at TIMESTAMPTZ,
    last_used_step BIGINT
);

CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
    agent_id UUID NOT NULL REFERENCES agent_mfa(agent_id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL CHECK (btrim(code_hash) <> ''),
    created_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    PRIMARY KEY (agent_id, code_hash)
);
