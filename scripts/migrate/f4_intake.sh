#!/usr/bin/env bash
#
# F4 data migration: sources, intake jobs, records, errors and files move from
# leads_db to intake_db with the same ids, together with the organizations whose
# default sources already exist and the tenant events already applied. Does steps
# 4 (copy) and 5 (verify) of the procedure in docs/content/microservices/06-plan-de-desacople.md.
#
# Left to whoever operates the cut, in this order:
#   1    drain: `docker compose stop gateway` so nothing new arrives, then let
#        backend-worker publish the `job` outbox and IntakeRejected, and let
#        intake-worker empty intake.jobs (the script refuses while any is left:
#        a job message read by the old worker after the copy would write leads_db);
#   2    freeze: `docker compose stop backend-worker intake-worker`;
#   3    the service's migrations: `docker compose up -d db-bootstrap identity intake`
#        and wait for both to be healthy (identity is recreated so it knows the
#        intake service client; without it every admission is refused);
#   6    cut: merge the backend's removal of intake (X2), then
#        `docker compose up -d --build intake-worker backend-worker gateway`
#        and run ./scripts/verify-e2e.sh.
#
# Precondition: frozen. It refuses to run while gateway, backend-worker or
# intake-worker is running: before the cut a live writer would leave the copy
# behind, and after it the truncate would delete what intake wrote since. The
# intake API may run (it applies the migrations): with the gateway stopped no
# request reaches it. While frozen it is repeatable: it truncates the target and
# only reads the source.
# Exits non-zero if any count or digest differs between the two databases.
set -euo pipefail
cd "$(dirname "$0")/../.."

running=$(docker compose ps --status running --format '{{.Service}}' gateway backend-worker intake-worker)
if [ -n "$running" ]; then
  printf 'Refusing to copy: running now: %s.\n' "$(printf '%s' "$running" | tr '\n' ' ' | sed 's/ $//')"
  printf 'Drain and freeze first (docker compose stop gateway backend-worker intake-worker), or the cut is already done.\n'
  exit 1
fi

# The postgres superuser bypasses the REVOKE CONNECT on intake_db.
sql() { docker compose exec -T db psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -qAt -c "$2"; }

# Only these two kinds: after the cut nothing in the backend relays a job or an
# IntakeRejected from leads_db, while its own lead events keep being relayed there.
pending=$(sql leads_db "SELECT count(*) FROM outbox_events WHERE published_at IS NULL
                        AND (channel = 'job' OR (channel = 'internal' AND event_type = 'IntakeRejected'))")
if [ "$pending" != 0 ]; then
  printf 'Refusing to copy: %s job or IntakeRejected event(s) still unpublished in leads_db.\n' "$pending"
  printf 'Start backend-worker (and intake-worker) until they drain, then freeze again.\n'
  exit 1
fi

# RabbitMQ stays up through the cut. A stopped consumer returns its unacked
# message to ready, so both columns are read; an absent queue counts as empty.
if ! queues=$(docker compose exec -T rabbitmq rabbitmqctl list_queues -q name messages_ready messages_unacknowledged); then
  printf 'Refusing to copy: cannot read the intake.jobs queue (is rabbitmq running?).\n'
  exit 1
fi
queued=$(printf '%s\n' "$queues" | awk '$1 == "intake.jobs" {n += $2 + $3} END {print n + 0}')
if [ "$queued" != 0 ]; then
  printf 'Refusing to copy: intake.jobs still holds %s message(s).\n' "$queued"
  printf 'Start intake-worker until the queue is empty, then freeze again.\n'
  exit 1
fi

# Any outbox row in intake_db is a write intake made after a previous cut:
# truncating now would delete it, so a stopped stack is not enough to proceed.
written=$(sql intake_db "SELECT count(*) FROM outbox_events")
if [ "$written" != 0 ]; then
  printf 'Refusing to copy: intake_db already has %s outbox row(s), so the cut is done.\n' "$written"
  exit 1
fi

# copy <select on leads_db> <table(columns) in intake_db>
copy() {
  sql leads_db "COPY ($1) TO STDOUT" | sql intake_db "COPY $2 FROM STDIN"
}

failures=0
# verify <label> <query on leads_db> <query on intake_db>
verify() {
  local src dst
  src=$(sql leads_db "$2")
  dst=$(sql intake_db "$3")
  if [ "$src" = "$dst" ]; then
    printf '  ok    %-28s %s\n' "$1" "$src"
  else
    printf '  FAIL  %-28s source=%s target=%s\n' "$1" "$src" "$dst"
    failures=$((failures + 1))
  fi
}

printf 'Truncating intake_db…\n'
# outbox_events and processed_events too: a rerun must not keep rows from a previous attempt.
sql intake_db "TRUNCATE lead_sources, intake_jobs, intake_records, intake_errors, intake_files,
               provisioned_tenants, outbox_events, processed_events CASCADE"

printf 'Copying…\n'
# Parents first: the target keeps its internal foreign keys.
copy "SELECT id, tenant_id, name, kind, field_mapping, secret_hash, is_active, created_at, updated_at FROM lead_sources" \
  "lead_sources (id, tenant_id, name, kind, field_mapping, secret_hash, is_active, created_at, updated_at)"
copy "SELECT tenant_id, provisioned_at FROM provisioned_tenants" \
  "provisioned_tenants (tenant_id, provisioned_at)"
copy "SELECT id, tenant_id, source_id, kind, status, total_items, succeeded, failed, created_at, completed_at,
             correlation_id FROM intake_jobs" \
  "intake_jobs (id, tenant_id, source_id, kind, status, total_items, succeeded, failed, created_at, completed_at,
                correlation_id)"
# lead_id travels as a plain UUID: in intake_db it references nothing.
copy "SELECT id, tenant_id, source_id, payload, status, lead_id, received_at, processed_at, job_id FROM intake_records" \
  "intake_records (id, tenant_id, source_id, payload, status, lead_id, received_at, processed_at, job_id)"
copy "SELECT id, intake_record_id, field, received_value, message, error_code FROM intake_errors" \
  "intake_errors (id, intake_record_id, field, received_value, message, error_code)"
copy "SELECT job_id, tenant_id, filename, content, size_bytes, parsed_at FROM intake_files" \
  "intake_files (job_id, tenant_id, filename, content, size_bytes, parsed_at)"
# The consumer group keeps its committed offsets, so a tenant event replayed
# from the compacted topic must still be recognised as already applied.
copy "SELECT consumer, event_id, processed_at FROM processed_events WHERE consumer = 'intake.tenants'" \
  "processed_events (consumer, event_id, processed_at)"

printf 'Verifying…\n'
# digest <key expression> <table> — row count plus an md5 over the ordered keys.
# concat_ws, not ||: a NULL (total_items, lead_id) would otherwise drop the whole row from the digest.
digest() { printf "SELECT count(*) || ' rows, md5 ' || coalesce(md5(string_agg(%s, ',' ORDER BY %s)), '-') FROM %s" "$1" "$1" "$2"; }
check_table() { verify "$1" "$(digest "$2" "$3")" "$(digest "$2" "$3")"; }
check_table lead_sources "concat_ws('/', id, tenant_id, is_active)" lead_sources
check_table provisioned_tenants "tenant_id::text" provisioned_tenants
check_table intake_jobs "concat_ws('/', id, source_id, status, total_items, succeeded, failed)" intake_jobs
check_table intake_records "concat_ws('/', id, job_id, status, lead_id)" intake_records
check_table intake_errors "concat_ws('/', id, intake_record_id)" intake_errors
check_table intake_files "concat_ws('/', job_id, md5(content))" intake_files
check_table "processed (intake.tenants)" "event_id::text" \
  "(SELECT event_id FROM processed_events WHERE consumer = 'intake.tenants') AS p"

if [ "$failures" -ne 0 ]; then
  printf '%s checks failed: do not cut over.\n' "$failures"
  exit 1
fi
printf 'Copy verified.\n'
