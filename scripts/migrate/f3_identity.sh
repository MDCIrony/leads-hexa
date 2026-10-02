#!/usr/bin/env bash
#
# F3 data migration: tenants, agents and everything that authenticates them move
# from leads_db to identity_db with the same ids. Does steps 4 (copy) and 5
# (verify) of the procedure in docs/content/microservices/06-plan-de-desacople.md.
# Active sessions travel too, so nobody has to sign in again after the cut.
#
# Left to whoever operates the cut, in this order:
#   1    drain: backend-worker publishes every pending internal event (the script
#        refuses while any is left, so no AgentState is lost between the two outboxes);
#   2    freeze: `docker compose stop gateway backend-worker`;
#   3    the service's migrations: `docker compose up -d db-bootstrap identity`
#        and wait for it to be healthy;
#   6    cut: point the gateway at identity, start identity-worker, backend-worker and gateway.
#
# Precondition: frozen. It refuses to run while identity-worker, backend-worker
# or gateway is running: before the cut a live writer would leave the copy
# behind, and after it the truncate would delete what identity wrote since.
# While frozen it is repeatable: it truncates the target and only reads the source.
# Exits non-zero if any count or id digest differs between the two databases.
set -euo pipefail
cd "$(dirname "$0")/../.."

running=$(docker compose ps --status running --format '{{.Service}}' identity-worker backend-worker gateway)
if [ -n "$running" ]; then
  printf 'Refusing to copy: running now: %s.\n' "$(printf '%s' "$running" | tr '\n' ' ' | sed 's/ $//')"
  printf 'Freeze first (docker compose stop gateway backend-worker), or the cut is already done.\n'
  exit 1
fi

# The postgres superuser bypasses the REVOKE CONNECT on identity_db.
sql() { docker compose exec -T db psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -qAt -c "$2"; }

pending=$(sql leads_db "SELECT count(*) FROM outbox_events WHERE channel = 'internal' AND published_at IS NULL")
if [ "$pending" != 0 ]; then
  printf 'Refusing to copy: %s internal event(s) still unpublished in leads_db.\n' "$pending"
  printf 'Start backend-worker until they drain, then freeze again.\n'
  exit 1
fi

# copy <select on leads_db> <table(columns) in identity_db>
copy() {
  sql leads_db "COPY ($1) TO STDOUT" | sql identity_db "COPY $2 FROM STDIN"
}

failures=0
# verify <label> <query on leads_db> <query on identity_db>
verify() {
  local src dst
  src=$(sql leads_db "$2")
  dst=$(sql identity_db "$3")
  if [ "$src" = "$dst" ]; then
    printf '  ok    %-28s %s\n' "$1" "$src"
  else
    printf '  FAIL  %-28s source=%s target=%s\n' "$1" "$src" "$dst"
    failures=$((failures + 1))
  fi
}

printf 'Truncating identity_db…\n'
# outbox_events too: a rerun must not keep rows identity wrote in a previous attempt.
sql identity_db "TRUNCATE tenants, agents, auth_sessions, auth_challenges, agent_mfa, mfa_recovery_codes,
                 social_identities, outbox_events CASCADE"

printf 'Copying…\n'
# Parents first: the target keeps its foreign keys.
copy "SELECT id, name, slug, is_active, created_at, version FROM tenants" \
  "tenants (id, name, slug, is_active, created_at, version)"
# Without group_id: the group is lead-core's now (ADR-0036), kept in advisors.
copy "SELECT id, name, email, is_active, role, hashed_password, tenant_id, version FROM agents" \
  "agents (id, name, email, is_active, role, hashed_password, tenant_id, version)"
copy "SELECT token_hash, agent_id, created_at, expires_at, revoked_at FROM auth_sessions" \
  "auth_sessions (token_hash, agent_id, created_at, expires_at, revoked_at)"
copy "SELECT token_hash, agent_id, purpose, attempts, expires_at, consumed_at, created_at, provider, state_hash,
             pkce_verifier, return_path FROM auth_challenges" \
  "auth_challenges (token_hash, agent_id, purpose, attempts, expires_at, consumed_at, created_at, provider,
                    state_hash, pkce_verifier, return_path)"
copy "SELECT agent_id, secret_ciphertext, enabled_at, last_used_step FROM agent_mfa" \
  "agent_mfa (agent_id, secret_ciphertext, enabled_at, last_used_step)"
copy "SELECT agent_id, code_hash, created_at, used_at FROM mfa_recovery_codes" \
  "mfa_recovery_codes (agent_id, code_hash, created_at, used_at)"
copy "SELECT id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at FROM social_identities" \
  "social_identities (id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at)"

printf 'Verifying…\n'
# digest <key expression> <table> — row count plus an md5 over the ordered keys.
digest() { printf "SELECT count(*) || ' rows, md5 ' || coalesce(md5(string_agg(%s, ',' ORDER BY %s)), '-') FROM %s" "$1" "$1" "$2"; }
verify tenants "$(digest "id::text || '/' || version" tenants)" "$(digest "id::text || '/' || version" tenants)"
verify agents "$(digest "id::text || '/' || version || '/' || is_active" agents)" \
  "$(digest "id::text || '/' || version || '/' || is_active" agents)"
active="(SELECT token_hash FROM auth_sessions WHERE revoked_at IS NULL AND expires_at > now()) AS s"
verify "active sessions" "$(digest token_hash "$active")" "$(digest token_hash "$active")"
verify auth_sessions "$(digest token_hash auth_sessions)" "$(digest token_hash auth_sessions)"
verify auth_challenges "$(digest token_hash auth_challenges)" "$(digest token_hash auth_challenges)"
verify agent_mfa "$(digest "agent_id::text" agent_mfa)" "$(digest "agent_id::text" agent_mfa)"
verify mfa_recovery_codes "$(digest code_hash mfa_recovery_codes)" "$(digest code_hash mfa_recovery_codes)"
verify social_identities "$(digest "id::text" social_identities)" "$(digest "id::text" social_identities)"

if [ "$failures" -ne 0 ]; then
  printf '%s checks failed: do not cut over.\n' "$failures"
  exit 1
fi
printf 'Copy verified.\n'
