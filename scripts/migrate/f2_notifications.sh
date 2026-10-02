#!/usr/bin/env bash
#
# F2 data migration: the inbox moves from leads_db to notifications_db with the
# same ids. Does steps 4 (copy) and 5 (verify) of the procedure in
# docs/content/microservices/06-plan-de-desacople.md.
#
# Left to whoever operates the cut, in this order:
#   1-2  drain and freeze: `docker compose stop gateway backend-worker`;
#   3    the service's migrations: `docker compose up -d db-bootstrap notifications`
#        and wait for it to be healthy;
#   6    cut: start notifications-worker, backend-worker and gateway.
#
# Precondition: frozen. It refuses to run while notifications-worker,
# backend-worker or gateway is running: before the cut a live consumer would
# leave processed_events incomplete, and after it the truncate would delete the
# notices written since. While frozen it is repeatable: it truncates the target
# before copying and only reads the source.
# Exits non-zero if any count or id digest differs between the two databases.
set -euo pipefail
cd "$(dirname "$0")/../.."

running=$(docker compose ps --status running --format '{{.Service}}' notifications-worker backend-worker gateway)
if [ -n "$running" ]; then
  printf 'Refusing to copy: running now: %s.\n' "$(printf '%s' "$running" | tr '\n' ' ' | sed 's/ $//')"
  printf 'Freeze first (docker compose stop gateway backend-worker), or the cut is already done.\n'
  exit 1
fi

PROCESSED_CONSUMERS="'notifications.lead-events', 'notifications.intake-events'"

# The postgres superuser bypasses the REVOKE CONNECT on notifications_db.
sql() { docker compose exec -T db psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -qAt -c "$2"; }

# copy <select on leads_db> <table(columns) in notifications_db>
copy() {
  sql leads_db "COPY ($1) TO STDOUT" | sql notifications_db "COPY $2 FROM STDIN"
}

failures=0
# verify <label> <query on leads_db> <query on notifications_db>
verify() {
  local src dst
  src=$(sql leads_db "$2")
  dst=$(sql notifications_db "$3")
  if [ "$src" = "$dst" ]; then
    printf '  ok    %-34s %s\n' "$1" "$src"
  else
    printf '  FAIL  %-34s source=%s target=%s\n' "$1" "$src" "$dst"
    failures=$((failures + 1))
  fi
}

printf 'Truncating notifications_db…\n'
sql notifications_db "TRUNCATE notifications, members, processed_events"

printf 'Copying…\n'
copy "SELECT id, tenant_id, recipient_id, kind, lead_id, intake_record_id, message, is_read, created_at
      FROM notifications" \
  "notifications (id, tenant_id, recipient_id, kind, lead_id, intake_record_id, message, is_read, created_at)"
copy "SELECT consumer, event_id, processed_at FROM processed_events WHERE consumer IN ($PROCESSED_CONSUMERS)" \
  "processed_events (consumer, event_id, processed_at)"
# The whole projection at the cut; from here the compacted topic keeps it, and
# the version gate makes its replay of older states harmless.
copy "SELECT id AS agent_id, tenant_id, role, is_active, version FROM agents WHERE tenant_id IS NOT NULL" \
  "members (agent_id, tenant_id, role, is_active, version)"

printf 'Verifying…\n'
by_reader="SELECT count(*) || ' groups, md5 ' || coalesce(md5(string_agg(recipient_id || '/' || is_read || '=' || n,
  ',' ORDER BY recipient_id, is_read)), '-')
  FROM (SELECT recipient_id, is_read, count(*) AS n FROM notifications GROUP BY 1, 2) AS g"
verify "notifications by (recipient, is_read)" "$by_reader" "$by_reader"
ids="SELECT count(*) || ' rows, md5 ' || coalesce(md5(string_agg(id::text, ',' ORDER BY id)), '-') FROM notifications"
verify "notifications ids" "$ids" "$ids"
verify "processed_events" \
  "SELECT count(*) || ' rows, md5 ' || coalesce(md5(string_agg(consumer || '/' || event_id, ',' ORDER BY consumer, event_id)), '-')
   FROM processed_events WHERE consumer IN ($PROCESSED_CONSUMERS)" \
  "SELECT count(*) || ' rows, md5 ' || coalesce(md5(string_agg(consumer || '/' || event_id, ',' ORDER BY consumer, event_id)), '-')
   FROM processed_events"
verify "members" \
  "SELECT count(*) || ' rows, md5 ' || coalesce(md5(string_agg(id::text, ',' ORDER BY id)), '-')
   FROM agents WHERE tenant_id IS NOT NULL" \
  "SELECT count(*) || ' rows, md5 ' || coalesce(md5(string_agg(agent_id::text, ',' ORDER BY agent_id)), '-') FROM members"

if [ "$failures" -ne 0 ]; then
  printf '%s checks failed: do not cut over.\n' "$failures"
  exit 1
fi
printf 'Copy verified.\n'
