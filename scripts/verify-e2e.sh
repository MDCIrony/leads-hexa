#!/usr/bin/env bash
#
# End-to-end business verification against a running stack.
#
# This is the trust harness: it asserts what the pytest suite cannot, namely
# that the whole circuit behaves over real HTTP with real sessions. It is meant to
# GROW — each phase appends its own verify_fN function and calls it from main.
# Never rewrite it from scratch; extend it.
#
#   ./scripts/verify-e2e.sh            run against the current stack
#   ./scripts/verify-e2e.sh --reset    recreate the volume first (phase closing)
#
# Runs are independent: every entity is suffixed with a per-run stamp, so the
# script does not need a clean database to give a correct answer.

set -u

API=${API:-http://localhost:8001/api/v1}
STAMP=$(date +%s)
ADMIN_PASS=Secret123
FAILURES=0

# ---------------------------------------------------------------- helpers ---

req() {
  local args=() arg session
  while [ "$#" -gt 0 ]; do
    arg=$1
    if [ "$arg" = "-H" ] && [ "$#" -ge 2 ] && [[ "$2" == 'Authorization: Bearer '* ]]; then
      session=${2#Authorization: Bearer }
      if [ -f "$session" ]; then
        args+=(-b "$session")
      else
        args+=(-H "$2")
      fi
      shift 2
      continue
    fi
    if [[ "$arg" == 'Authorization: Bearer '* ]]; then
      session=${arg#Authorization: Bearer }
      if [ -f "$session" ]; then
        args+=(-b "$session")
      else
        args+=("$arg")
      fi
    else
      args+=("$arg")
    fi
    shift
  done
  curl -s -w '\n%{http_code}' "${args[@]}"
}
code() { printf '%s' "$1" | tail -1; }
body() { printf '%s' "$1" | sed '$d'; }

# Reads one expression out of a JSON body. Prints nothing on malformed input
# instead of dumping a traceback, so a failing step stays readable.
f() {
  python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit()
print($1)
" 2>/dev/null
}

oauth_state() {
  python3 -c 'import sys; from urllib.parse import parse_qs, urlsplit; print(parse_qs(urlsplit(sys.argv[1]).query).get("state", [""])[0])' "$1"
}

login() {
  local jar body_file status
  jar=$(mktemp "/tmp/leads-e2e-${STAMP}-XXXXXX.cookies")
  body_file="${jar}.login"
  status=$(curl -s -o "$body_file" -w '%{http_code}' -c "$jar" -X POST "$API/auth/login" \
    --data-urlencode "username=$1" \
    --data-urlencode "password=$2")
  if [[ "$status" =~ ^2 ]] && grep -q $'\tleads_session\t' "$jar"; then
    printf '%s' "$jar"
  else
    rm -f "$jar" "$body_file"
  fi
}

# check <description> <expected> <actual>
check() {
  if [ "$2" = "$3" ]; then
    printf '  \033[32m✓\033[0m %-52s %s\n' "$1" "$3"
  else
    printf '  \033[31m✗\033[0m %-52s got %s, expected %s\n' "$1" "$3" "$2"
    FAILURES=$((FAILURES + 1))
  fi
}

section() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# await_job <session> <job_id> — waits until a job reaches a terminal status.
# Bounded polling, never a fixed sleep: a short one makes the harness flaky,
# a long one makes it useless. Unlike TestClient in the pytest suite, this
# script talks to a real running container, where the background task genuinely
# runs after the response is sent.
await_job() {
  local i r st
  for i in $(seq 1 30); do
    r=$(req "$API/intake/jobs/$2" -H "Authorization: Bearer $1")
    st=$(body "$r" | f 'd.get("status")')
    case "$st" in COMPLETED|FAILED) printf '%s' "$st"; return 0 ;; esac
    sleep 0.2
  done
  printf 'TIMEOUT'
}

# await_notice <session> <expression over d> — waits until the inbox satisfies it.
# Notifications are written by backend-worker once Kafka delivers the event: one
# hop after the job completes, so the reads below must not race it. Bounded
# polling like await_job; the check that follows still decides pass or fail.
await_notice() {
  local i r
  for i in $(seq 1 50); do
    r=$(req "$API/notifications" -H "Authorization: Bearer $1")
    [ "$(body "$r" | f "bool($2)")" = True ] && return 0
    sleep 0.2
  done
}

# await_quiet <session> — waits until the inbox counter stops moving.
# A baseline read right after earlier phases can predate a notification they
# caused that is still on its way through Kafka; a counter unchanged for the
# whole window (longer than a relay pass plus a consumer fetch) is a baseline
# that later "+1" checks can trust.
await_quiet() {
  local i r now last="" stable=0
  for i in $(seq 1 60); do
    r=$(req "$API/notifications" -H "Authorization: Bearer $1")
    now=$(body "$r" | f 'd.get("unread_count")')
    if [ "$now" = "$last" ]; then stable=$((stable + 1)); else stable=0; fi
    [ "$stable" -ge 10 ] && return 0
    last=$now
    sleep 0.25
  done
}

# ------------------------------------------------------------- scaffolding ---

# Platform admin, two organizations, three agents. Everything later builds on
# the variables this exports.
bootstrap() {
  section "Escenario base"

  # The very first agent is created unauthenticated; on a database that already
  # has one, that same call is refused and we log in instead.
  local r
  r=$(req -X POST "$API/agents/" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Root\",\"email\":\"root@plat.test\",\"password\":\"$ADMIN_PASS\",\"role\":\"ADMIN\"}")
  case "$(code "$r")" in
    201) printf '  · admin de plataforma creado\n' ;;
    *) printf '  · admin de plataforma ya existía\n' ;;
  esac
  ADMIN_TOKEN=$(login root@plat.test "$ADMIN_PASS")
  [ -n "$ADMIN_TOKEN" ] || { printf '  \033[31m✗ sin sesión de admin: abortando\033[0m\n'; exit 1; }

  r=$(req -X POST "$API/tenants" -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
    -d "{\"name\":\"OrgA-$STAMP\",\"manager\":{\"name\":\"MgrA\",\"email\":\"  MGR-A-$STAMP@X.TEST  \",\"password\":\"$ADMIN_PASS\"}}")
  check "organización A creada" 201 "$(code "$r")"
  check "correo del gestor canonicalizado" "mgr-a-$STAMP@x.test" "$(body "$r" | f 'd["manager"]["email"]')"
  TENANT_A=$(body "$r" | f 'd["id"]')
  MGR_A=$(login " mGr-A-$STAMP@x.Test " "$ADMIN_PASS")
  check "gestor entra con correo normalizado" True "$(test -n "$MGR_A" && printf True || printf False)"

  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Uno\",\"email\":\"  UNO-$STAMP@X.TEST  \",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  AGENT_1=$(body "$r" | f 'd["id"]')
  check "asesor uno" 201 "$(code "$r")"
  check "correo del asesor canonicalizado" "uno-$STAMP@x.test" "$(body "$r" | f 'd["email"]')"

  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Dos\",\"email\":\"dos-$STAMP@x.test\",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  AGENT_2=$(body "$r" | f 'd["id"]')
  check "asesor dos" 201 "$(code "$r")"

  TOKEN_1=$(login " uNo-$STAMP@X.Test " "$ADMIN_PASS")
  check "asesor entra con correo normalizado" True "$(test -n "$TOKEN_1" && printf True || printf False)"
  TOKEN_2=$(login "dos-$STAMP@x.test" "$ADMIN_PASS")

  # Second organization: the control that proves isolation.
  r=$(req -X POST "$API/tenants" -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
    -d "{\"name\":\"OrgB-$STAMP\",\"manager\":{\"name\":\"MgrB\",\"email\":\"mgr-b-$STAMP@x.test\",\"password\":\"$ADMIN_PASS\"}}")
  check "organización B creada" 201 "$(code "$r")"
  MGR_B=$(login "mgr-b-$STAMP@x.test" "$ADMIN_PASS")

  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_B" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Beto\",\"email\":\"beto-$STAMP@x.test\",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  AGENT_B=$(body "$r" | f 'd["id"]')
  check "asesor de la organización B" 201 "$(code "$r")"
}

# -------------------------------------------------------------- sessions ---
# Opaque browser sessions (ADR-0029, Fase 1): cookie flags, rehydration via
# /auth/me, idempotent logout, per-session independence and hostile-Origin
# rejection. Small on purpose: the full matrix lives in the pytest suite.

verify_sessions() {
  local r jar2 headers_file
  section "Sesiones opacas"

  headers_file=$(mktemp "/tmp/leads-e2e-${STAMP}-XXXXXX.headers")
  r=$(curl -s -D "$headers_file" -o /dev/null -w '%{http_code}' -c "$headers_file.cookies" \
    -X POST "$API/auth/login" \
    --data-urlencode "username=mgr-a-$STAMP@x.test" \
    --data-urlencode "password=$ADMIN_PASS")
  check "el login responde 200" 200 "$r"
  check "la cookie es HttpOnly" True "$(grep -qi 'httponly' "$headers_file" && printf True || printf False)"
  check "la cookie es SameSite=Lax" True "$(grep -qi 'samesite=lax' "$headers_file" && printf True || printf False)"
  check "la cookie cubre Path=/" True "$(grep -qi 'path=/' "$headers_file" && printf True || printf False)"
  rm -f "$headers_file" "$headers_file.cookies"

  r=$(req -X POST "$API/auth/login" \
    --data-urlencode "username=mgr-a-$STAMP@x.test" \
    --data-urlencode "password=$ADMIN_PASS")
  check "el cuerpo es solo el estado" '{"status": "AUTHENTICATED"}' "$(body "$r" | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin), sort_keys=True))' 2>/dev/null)"
  check "el cuerpo no trae token" "" "$(body "$r" | f 'd.get("access_token") or ""')"

  r=$(req "$API/auth/me" -H "Authorization: Bearer $MGR_A")
  check "la sesión rehidrata en /me" 200 "$(code "$r")"
  check "la identidad sale de la sesión" "mgr-a-$STAMP@x.test" "$(body "$r" | f 'd.get("email")')"

  jar2=$(login "mgr-a-$STAMP@x.test" "$ADMIN_PASS")
  r=$(req -X POST "$API/auth/logout" -H "Authorization: Bearer $MGR_A")
  check "el logout responde 204" 204 "$(code "$r")"
  r=$(req "$API/auth/me" -H "Authorization: Bearer $MGR_A")
  check "la cookie usada no rehidrata" 401 "$(code "$r")"
  r=$(req "$API/auth/me" -H "Authorization: Bearer $jar2")
  check "la otra sesión sigue viva" 200 "$(code "$r")"
  MGR_A=$jar2

  r=$(req -X POST "$API/auth/login" -H "Origin: https://evil.test" \
    --data-urlencode "username=mgr-a-$STAMP@x.test" \
    --data-urlencode "password=$ADMIN_PASS")
  check "el origen hostil no entra" 403 "$(code "$r")"
  check "el rechazo lleva su código" FORBIDDEN "$(body "$r" | f 'd.get("error_code")')"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H "Origin: https://evil.test" \
    -H 'Content-Type: application/json' -d '{"name":"x","conditions":[],"score_delta":1}')
  check "el origen hostil no muta" 403 "$(code "$r")"
  r=$(req "$API/auth/me" -H "Authorization: Bearer $MGR_A")
  check "la sesión sobrevive al rechazo" 200 "$(code "$r")"

  r=$(req -X POST "$API/auth/logout" -H "Authorization: Bearer $MGR_A" -H "Origin: https://evil.test")
  check "el logout hostil no revoca" 403 "$(code "$r")"
  r=$(req "$API/auth/me" -H "Authorization: Bearer $MGR_A")
  check "la sesión sigue tras el logout hostil" 200 "$(code "$r")"
}

# -------------------------------------------------------------------- F0 ---
# Email identity is canonical globally: it is the login key, not a label a
# different organization may reuse.

verify_f0_identity() {
  local r
  section "F0 · identidad por correo"

  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Duplicado A\",\"email\":\" uNo-$STAMP@x.test \",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  check "duplicado normalizado en la misma organización" 400 "$(code "$r")"
  check "duplicado local informa su código" EMAIL_ALREADY_EXISTS "$(body "$r" | f 'd.get("error_code")')"

  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_B" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Duplicado B\",\"email\":\"UNO-$STAMP@X.TEST\",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  check "duplicado normalizado en otra organización" 400 "$(code "$r")"
  check "duplicado global informa su código" EMAIL_ALREADY_EXISTS "$(body "$r" | f 'd.get("error_code")')"
}

# ------------------------------------------------------------------- F2a ---
# Scoring that actually fires, the lead lifecycle, and cross-organization
# isolation answering 404 rather than 403.

verify_f2a() {
  local r job
  section "F2a · reglas de puntuación"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"tech o saas","conditions":[{"field":"industry","operator":"IN","value":["Tech","SaaS"]}],"score_delta":40,"priority":10}')
  check "IN acepta una lista" 201 "$(code "$r")"
  check "IN la almacena como lista, no como texto" "['Tech', 'SaaS']" "$(body "$r" | f '(d.get("conditions") or [{}])[0].get("value")')"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"presupuesto alto","conditions":[{"field":"budget","operator":"GREATER_THAN","value":5000}],"score_delta":25,"priority":5}')
  check "GREATER_THAN conserva el número" 5000 "$(body "$r" | f '(d.get("conditions") or [{}])[0].get("value")')"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"inactiva","conditions":[{"field":"company","operator":"EQUALS","value":"Acme"}],"score_delta":99,"is_active":false}')
  check "regla inactiva se acepta" 201 "$(code "$r")"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"no puntuable","conditions":[{"field":"tenant_id","operator":"EQUALS","value":"x"}],"score_delta":10}')
  check "un campo interno no es puntuable" FIELD_NOT_SCORABLE "$(body "$r" | f 'd.get("error_code")')"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"IN mal","conditions":[{"field":"industry","operator":"IN","value":"Tech"}],"score_delta":10}')
  check "IN exige una lista" INVALID_RULE_VALUE "$(body "$r" | f 'd.get("error_code")')"

  section "F2a · ingesta sin regla de asignación"

  r=$(req -X POST "$API/intake/leads/ingest" -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $MGR_A" \
    -d '{"first_name":"Ana","last_name":"Diaz","email":"ana@lead.test","company":"Acme","industry":"Tech","budget":9000}')
  check "el lead se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"

  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  LEAD=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')

  r=$(req "$API/leads/$LEAD" -H "Authorization: Bearer $MGR_A")
  check "sin asesor queda UNASSIGNED" UNASSIGNED "$(body "$r" | f 'd.get("status")')"
  check "puntúa 40+25 y la inactiva no cuenta" 65 "$(body "$r" | f 'd.get("score")')"
  check "applied_rules_count es real" 2 "$(body "$r" | f 'len(d.get("score_breakdown") or [])')"
  check "el gestor ve el desglose" 2 "$(body "$r" | f 'len(d.get("score_breakdown") or [])')"

  section "F2a · ciclo de vida"

  r=$(req -X POST "$API/leads/$LEAD/assign" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' -d "{\"agent_id\":\"$AGENT_1\"}")
  check "asignación manual" ASSIGNED "$(body "$r" | f 'd.get("status")')"
  check "deja traza del momento" True "$(body "$r" | f 'd.get("assigned_at") is not None')"

  r=$(req -X POST "$API/leads/$LEAD/assign" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' -d "{\"agent_id\":\"$AGENT_2\"}")
  check "reasignar a otro asesor" True "$(body "$r" | f "d.get('assigned_agent_id')=='$AGENT_2'")"

  section "F2a · aislamiento entre organizaciones (404, nunca 403)"

  r=$(req -X POST "$API/leads/$LEAD/assign" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' -d "{\"agent_id\":\"$AGENT_B\"}")
  check "asignar a un asesor ajeno" 404 "$(code "$r")"
  r=$(req "$API/leads/$LEAD" -H "Authorization: Bearer $MGR_B")
  check "gestor ajeno lee el lead" 404 "$(code "$r")"
  r=$(req "$API/leads/$LEAD" -H "Authorization: Bearer $TOKEN_1")
  check "asesor lee el lead de un compañero" 404 "$(code "$r")"

  section "F2a · la cartera del asesor"

  r=$(req "$API/leads/mine" -H "Authorization: Bearer $TOKEN_2")
  check "el dueño lo ve" 1 "$(body "$r" | f 'd.get("total")')"
  r=$(req "$API/leads/mine" -H "Authorization: Bearer $TOKEN_1")
  check "el reasignado fuera no lo ve" 0 "$(body "$r" | f 'd.get("total")')"
  r=$(req "$API/leads/mine" -H "Authorization: Bearer $ADMIN_TOKEN")
  check "el ADMIN no alcanza dato operativo" 403 "$(code "$r")"

  section "F2a · descarte"

  r=$(req -X POST "$API/leads/$LEAD/discard" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' -d '{"reason":"   "}')
  check "el descarte exige motivo" DISCARD_WITHOUT_REASON "$(body "$r" | f 'd.get("error_code")')"
  r=$(req -X POST "$API/leads/$LEAD/discard" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' -d '{"reason":"duplicado en el CRM"}')
  check "descarte con motivo" DISCARDED "$(body "$r" | f 'd.get("status")')"
  r=$(req -X POST "$API/leads/$LEAD/assign" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' -d "{\"agent_id\":\"$AGENT_1\"}")
  check "un descartado no vuelve al reparto" INVALID_LEAD_TRANSITION "$(body "$r" | f 'd.get("error_code")')"
  r=$(req -X POST "$API/leads/$LEAD/discard" -H "Authorization: Bearer $TOKEN_1" -H 'Content-Type: application/json' -d '{"reason":"x"}')
  check "un asesor no descarta" 403 "$(code "$r")"
}

# ------------------------------------------------------------------- F2b ---
# Unified intake: nothing that comes in is lost, and nobody ingests without
# a credential. LeadSource, IntakeRecord, and the inbox that lets a manager
# correct and promote what didn't parse.

verify_f2b() {
  local r rec src total lead job
  section "F2b · la ingesta exige credencial"

  r=$(req -X POST "$API/intake/leads/ingest" -H 'Content-Type: application/json' \
    -d '{"first_name":"X","last_name":"Y","email":"x@y.test","company":"Acme","industry":"Tech","budget":1000}')
  check "sin credencial no se ingesta" 401 "$(code "$r")"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $TOKEN_1" -H 'Content-Type: application/json' \
    -d '{"first_name":"X","last_name":"Y","email":"x@y.test","company":"Acme","industry":"Tech","budget":1000}')
  check "un asesor no ingesta" 403 "$(code "$r")"

  section "F2b · los orígenes de la organización"

  r=$(req "$API/sources" -H "Authorization: Bearer $MGR_A")
  check "la organización nace con sus dos orígenes" 2 "$(body "$r" | f 'd["total"]')"
  src=$(body "$r" | f '[s["id"] for s in d["items"] if s["kind"] == "MANUAL_FORM"][0]')

  section "F2b · un lead sin correo no se pierde"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Sin","last_name":"Correo","company":"Acme","industry":"Tech","budget":2000}')
  check "un lead sin correo se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"

  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')

  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "el correo ausente llega como null" "" "$(body "$r" | f 'd.get("email") or ""')"
  check "el lead dice de qué origen vino" "$src" "$(body "$r" | f 'd["source_id"]')"

  section "F2b · lo que no se puede interpretar queda en la bandeja"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Jane","last_name":"Bad","email":"jane@@example.com","company":"Acme","industry":"Tech","budget":3000}')
  check "un correo mal formado ya no se pierde" 202 "$(code "$r")"
  check "pero deja un registro de ingesta" True "$(body "$r" | f 'bool((d.get("record_ids") or [None])[0])')"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  rec=$(body "$r" | f '(d.get("record_ids") or [""])[0]')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"

  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  check "y queda REJECTED para revisión" REJECTED "$(body "$r" | f '(d.get("items") or [{}])[0].get("status") or ""')"

  r=$(req "$API/intake/records?status=REJECTED" -H "Authorization: Bearer $MGR_A")
  check "aparece en la bandeja de rechazados" True "$(body "$r" | f 'any(i["id"] == "'"$rec"'" for i in d["items"])')"
  check "con el error de campo email" email "$(body "$r" | f 'next(i for i in d["items"] if i["id"] == "'"$rec"'")["errors"][0]["field"]')"

  r=$(req "$API/intake/records" -H "Authorization: Bearer $MGR_A")
  total=$(body "$r" | f 'd["total"]')

  r=$(req -X POST "$API/intake/records/$rec/promote" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"payload":{"first_name":"Jane","last_name":"Bad","email":"jane@example.com","company":"Acme","industry":"Tech","budget":3000}}')
  check "promoverlo con el correo corregido" 200 "$(code "$r")"
  lead=$(body "$r" | f 'd["lead_id"]')

  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "el lead promovido existe" 200 "$(code "$r")"

  r=$(req "$API/intake/records" -H "Authorization: Bearer $MGR_A")
  check "promover no duplica la fila" "$total" "$(body "$r" | f 'd["total"]')"

  section "F2b · formulario y carga masiva por el mismo pipeline"

  printf 'first_name,last_name,email,company,industry,budget\nBuena,Fila,ok-%s@x.test,Acme,Tech,5000\nMala,Fila,mala@@x.test,Acme,Tech,5000\n' \
    "$STAMP" > /tmp/leads-$STAMP.csv
  r=$(req -X POST "$API/intake/leads/batch-upload" -H "Authorization: Bearer $MGR_A" \
    -F "file=@/tmp/leads-$STAMP.csv")
  check "la carga se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  rm -f /tmp/leads-$STAMP.csv
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"

  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  check "la fila buena entra" 1 "$(body "$r" | f 'sum(1 for i in d.get("items") or [] if i.get("status") == "PROMOTED")')"
  check "la fila mala no se pierde" 1 "$(body "$r" | f 'sum(1 for i in d.get("items") or [] if i.get("status") == "REJECTED")')"
  # Identified by content (its email), not by row_number: IntakeRecord does
  # not keep the row's original position in the file.
  check "la fila mala deja registro" True "$(body "$r" | f 'any(i.get("status") == "REJECTED" and i.get("payload", {}).get("email") == "mala@@x.test" for i in d.get("items") or [])')"

  section "F2b · aislamiento y protección de los orígenes"

  r=$(req -X PATCH "$API/sources/$src" -H "Authorization: Bearer $MGR_B" -H 'Content-Type: application/json' -d '{"is_active":false}')
  check "un origen de otra organización" 404 "$(code "$r")"

  r=$(req -X DELETE "$API/sources/$src" -H "Authorization: Bearer $MGR_A")
  check "borrar un origen con leads" SOURCE_IN_USE "$(body "$r" | f 'd.get("error_code")')"
}

# ------------------------------------------------------------------- F2d ---
# Reception and processing on separate transactions: intake answers 202
# immediately with a job_id, a background task finishes the work, and the
# resulting job — finished or stalled — can be queried and relaunched.

verify_f2d() {
  local r job1 job2 job3 job4 lead

  section "F2d · ingesta unitaria"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Uni","last_name":"Taria","email":"uni-'"$STAMP"'@x.test","company":"Acme","industry":"Tech","budget":4000}')
  check "la ingesta unitaria se acepta" 202 "$(code "$r")"
  job1=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job1")"

  r=$(req "$API/intake/jobs/$job1" -H "Authorization: Bearer $MGR_A")
  check "total_items del trabajo" 1 "$(body "$r" | f 'd.get("total_items")')"
  check "succeeded del trabajo" 1 "$(body "$r" | f 'd.get("succeeded")')"

  r=$(req "$API/intake/records?job_id=$job1" -H "Authorization: Bearer $MGR_A")
  check "su registro queda PROMOTED" PROMOTED "$(body "$r" | f '(d.get("items") or [{}])[0].get("status") or ""')"
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "y el lead existe" 200 "$(code "$r")"

  section "F2d · carga masiva con una fila buena y una mala"

  printf 'first_name,last_name,email,company,industry,budget\nBuena,F2d,ok-f2d-%s@x.test,Acme,Tech,4500\nMala,F2d,mala-f2d@@x.test,Acme,Tech,4500\n' \
    "$STAMP" > /tmp/f2d-batch-$STAMP.csv
  r=$(req -X POST "$API/intake/leads/batch-upload" -H "Authorization: Bearer $MGR_A" \
    -F "file=@/tmp/f2d-batch-$STAMP.csv")
  check "la carga masiva se acepta" 202 "$(code "$r")"
  job2=$(body "$r" | f 'd.get("job_id") or ""')
  rm -f /tmp/f2d-batch-$STAMP.csv
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job2")"

  r=$(req "$API/intake/jobs/$job2" -H "Authorization: Bearer $MGR_A")
  check "total_items de la carga" 2 "$(body "$r" | f 'd.get("total_items")')"
  check "succeeded de la carga" 1 "$(body "$r" | f 'd.get("succeeded")')"
  check "failed de la carga" 1 "$(body "$r" | f 'd.get("failed")')"

  r=$(req "$API/intake/records?job_id=$job2" -H "Authorization: Bearer $MGR_A")
  check "una fila PROMOTED" 1 "$(body "$r" | f 'sum(1 for i in d.get("items") or [] if i.get("status") == "PROMOTED")')"
  check "una fila REJECTED con error de email" True "$(body "$r" | f 'any(i.get("status") == "REJECTED" and (i.get("errors") or [{}])[0].get("field") == "email" for i in d.get("items") or [])')"

  section "F2d · un correo mal formado ya no se pierde"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Jane","last_name":"F2d","email":"jane@@example.com","company":"Acme","industry":"Tech","budget":3500}')
  check "se acepta igualmente" 202 "$(code "$r")"
  job3=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job3")"

  r=$(req "$API/intake/records?job_id=$job3" -H "Authorization: Bearer $MGR_A")
  check "y el registro queda REJECTED" REJECTED "$(body "$r" | f '(d.get("items") or [{}])[0].get("status") or ""')"

  section "F2d · un fichero ilegible no rompe el trabajo"

  # .xlsx by name, not by content: PandasFileParser dispatches on the filename
  # extension (pandas_file_parser.py), and pd.read_csv is lenient enough to
  # accept arbitrary text as a one-column, zero-row file instead of raising.
  # Forcing the Excel reader on non-Excel bytes is what actually fails to parse.
  printf 'esto no es un csv ni un xlsx\x00\x01\x02' > /tmp/basura-$STAMP.xlsx
  r=$(req -X POST "$API/intake/leads/batch-upload" -H "Authorization: Bearer $MGR_A" \
    -F "file=@/tmp/basura-$STAMP.xlsx")
  check "el fichero ilegible se acepta sin 500" 202 "$(code "$r")"
  job4=$(body "$r" | f 'd.get("job_id") or ""')
  rm -f /tmp/basura-$STAMP.xlsx
  check "el trabajo queda FAILED" FAILED "$(await_job "$MGR_A" "$job4")"

  r=$(req "$API/intake/records?job_id=$job4" -H "Authorization: Bearer $MGR_A")
  check "sin registros" 0 "$(body "$r" | f 'd.get("total")')"

  section "F2d · consulta y reproceso de trabajos"

  r=$(req "$API/intake/jobs/$job1" -H "Authorization: Bearer $MGR_B")
  check "un trabajo de otra organización" 404 "$(code "$r")"

  r=$(req -X POST "$API/intake/jobs/$job1/reprocess" -H "Authorization: Bearer $MGR_A")
  check "reprocesar un trabajo ya terminado" INVALID_JOB_TRANSITION "$(body "$r" | f 'd.get("error_code")')"
}

# ------------------------------------------------------------------- F2c ---
# Composable rules: a disqualification stage that cuts the flow with a
# reason instead of a score, several conditions per rule (AND), assignment
# routed by attribute instead of band alone, and qualify() with no threshold
# of its own — so nothing processed can be left stuck at NEW.

verify_f2c() {
  local r job lead dq_rule_id assign_rule_id

  section "F2c · descalificación: alta de reglas"

  r=$(req -X POST "$API/rules/disqualification" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"Sin via de contacto","conditions":[{"field":"phone","operator":"IS_EMPTY"},{"field":"email","operator":"IS_EMPTY"}]}')
  check "dos condiciones IS_EMPTY se acepta" 201 "$(code "$r")"
  dq_rule_id=$(body "$r" | f 'd.get("id") or ""')

  r=$(req -X POST "$API/rules/disqualification" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"Vacia","conditions":[]}')
  check "una lista de condiciones vacía se rechaza" 400 "$(code "$r")"
  check "con el código INVALID_RULE_CONDITIONS" INVALID_RULE_CONDITIONS "$(body "$r" | f 'd.get("error_code")')"

  r=$(req -X POST "$API/rules/disqualification" -H "Authorization: Bearer $TOKEN_1" -H 'Content-Type: application/json' \
    -d '{"name":"Intento de asesor","conditions":[{"field":"phone","operator":"IS_EMPTY"}]}')
  check "un asesor no crea reglas de descalificación" 403 "$(code "$r")"

  r=$(req -X PATCH "$API/rules/disqualification/$dq_rule_id" -H "Authorization: Bearer $MGR_B" -H 'Content-Type: application/json' \
    -d '{"priority":5}')
  check "una regla de otra organización" 404 "$(code "$r")"

  section "F2c · descalificación: sin teléfono y sin correo (criterio 1)"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Sin","last_name":"Contacto","company":"Acme","industry":"Retail","budget":1000}')
  check "un lead sin teléfono ni correo se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "queda DISQUALIFIED" DISQUALIFIED "$(body "$r" | f 'd.get("status")')"
  check "el motivo es el nombre de la regla, no una puntuación" "Sin via de contacto" "$(body "$r" | f 'd.get("disqualification_reason")')"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Con","last_name":"Telefono","company":"Acme","industry":"Retail","budget":1000,"phone":"+573000000001"}')
  check "un lead con sólo teléfono se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "con sólo teléfono no se descalifica" True "$(body "$r" | f 'd.get("status") != "DISQUALIFIED"')"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Con","last_name":"Correo","company":"Acme","industry":"Retail","budget":1000,"email":"con-correo-'"$STAMP"'@x.test"}')
  check "un lead con sólo correo se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "con sólo correo no se descalifica" True "$(body "$r" | f 'd.get("status") != "DISQUALIFIED"')"

  section "F2c · puntuación con varias condiciones"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"Retail BigBox","conditions":[{"field":"industry","operator":"EQUALS","value":"Retail"},{"field":"company","operator":"EQUALS","value":"BigBox"}],"score_delta":15}')
  check "regla de puntuación con dos condiciones se acepta" 201 "$(code "$r")"
  # Not cleaned up via DELETE — harmless, each run uses a fresh tenant.

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Cumple","last_name":"Ambas","company":"BigBox","industry":"Retail","budget":1000,"phone":"+573000000002"}')
  check "el lead que cumple ambas se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "cumple las dos condiciones y suma" 15 "$(body "$r" | f 'd.get("score")')"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Cumple","last_name":"Solo Una","company":"Acme","industry":"Retail","budget":1000,"phone":"+573000000003"}')
  check "el lead que cumple sólo una se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "cumple sólo una condición y no suma" 0 "$(body "$r" | f 'd.get("score")')"

  section "F2c · reparto por condición de atributo (criterio 3)"

  r=$(req -X POST "$API/rules/assignment" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Referidos\",\"target_agent_ids\":[\"$AGENT_1\"],\"conditions\":[{\"field\":\"custom_attributes.channel\",\"operator\":\"EQUALS\",\"value\":\"referral\"}]}")
  check "regla de asignación con condición de canal se acepta" 201 "$(code "$r")"
  assign_rule_id=$(body "$r" | f 'd.get("id") or ""')

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Del","last_name":"Canal","company":"Acme","industry":"Retail","budget":1000,"phone":"+573000000004","custom_attributes":{"channel":"referral"}}')
  check "el lead de ese canal se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "el lead de ese canal va a ese equipo" "$AGENT_1" "$(body "$r" | f 'd.get("assigned_agent_id")')"

  section "F2c · ningún lead procesado queda en NEW (criterio 5)"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Puntuacion","last_name":"Baja","company":"Acme","industry":"Retail","budget":1000,"phone":"+573000000005"}')
  check "un lead de puntuación baja se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead" -H "Authorization: Bearer $MGR_A")
  check "nunca queda en NEW" True "$(body "$r" | f 'd.get("status") != "NEW"')"

  section "F2c · limpieza de las reglas propias"

  r=$(req -X DELETE "$API/rules/disqualification/$dq_rule_id" -H "Authorization: Bearer $MGR_A")
  check "borrar la regla de descalificación" 204 "$(code "$r")"

  r=$(req -X DELETE "$API/rules/assignment/$assign_rule_id" -H "Authorization: Bearer $MGR_A")
  check "borrar la regla de asignación" 204 "$(code "$r")"
}

# ------------------------------------------------------------------- F3a ---
# Notifications: the bell an agent or manager reads instead of hunting for
# what changed. AGENT_1/AGENT_2 already carry notices from the manual
# assign/reassign in verify_f2a and the channel routing in verify_f2c, so
# every check here is relative to a captured baseline, never to zero.

verify_f3a() {
  local r job base1 after_ingest notif_id lead_direct lead_orphan rec agent_tmp

  section "F3a · la bandeja del asesor"

  await_quiet "$TOKEN_1"
  r=$(req "$API/notifications" -H "Authorization: Bearer $TOKEN_1")
  check "el asesor uno consulta su bandeja al empezar" 200 "$(code "$r")"
  base1=$(body "$r" | f 'd.get("unread_count")')

  # F2c deleted the assignment rule it created, so nothing currently routes
  # to AGENT_1. The condition keeps this rule from also catching the
  # "orphan" lead ingested later in this same function.
  r=$(req -X POST "$API/rules/assignment" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"F3a directo\",\"target_agent_ids\":[\"$AGENT_1\"],\"conditions\":[{\"field\":\"custom_attributes.f3a\",\"operator\":\"EQUALS\",\"value\":\"direct\"}]}")
  check "regla F3a hacia el asesor uno" 201 "$(code "$r")"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"F3a","last_name":"Directo","company":"Acme","industry":"Retail","budget":1000,"phone":"+573000000010","custom_attributes":{"f3a":"direct"}}')
  check "el lead directo se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead_direct=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')

  await_notice "$TOKEN_1" "d.get('unread_count') == $((base1 + 1))"
  r=$(req "$API/notifications" -H "Authorization: Bearer $TOKEN_1")
  after_ingest=$(body "$r" | f 'd.get("unread_count")')
  check "su unread_count sube" "$((base1 + 1))" "$after_ingest"

  notif_id=$(body "$r" | f '(d.get("items") or [{}])[0].get("id") or ""')
  check "la notificación más reciente es LEAD_ASSIGNED" LEAD_ASSIGNED "$(body "$r" | f '(d.get("items") or [{}])[0].get("kind") or ""')"
  check "y trae el lead_id" "$lead_direct" "$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')"

  r=$(req "$API/notifications" -H "Authorization: Bearer $TOKEN_2")
  check "el otro asesor no ve esa notificación" False "$(body "$r" | f 'any(i.get("id") == "'"$notif_id"'" for i in d.get("items") or [])')"

  r=$(req -X POST "$API/notifications/$notif_id/read" -H "Authorization: Bearer $TOKEN_1")
  check "marcar una como leída" 204 "$(code "$r")"
  r=$(req "$API/notifications" -H "Authorization: Bearer $TOKEN_1")
  check "el contador baja" "$base1" "$(body "$r" | f 'd.get("unread_count")')"

  r=$(req -X POST "$API/notifications/$notif_id/read" -H "Authorization: Bearer $TOKEN_2")
  check "el otro asesor no puede marcarla (404, nunca 403)" 404 "$(code "$r")"

  r=$(req -X POST "$API/notifications/read-all" -H "Authorization: Bearer $TOKEN_1")
  check "marcar todas" 204 "$(code "$r")"
  r=$(req "$API/notifications" -H "Authorization: Bearer $TOKEN_1")
  check "el contador queda en cero" 0 "$(body "$r" | f 'd.get("unread_count")')"

  section "F3a · el gestor y el aislamiento entre organizaciones"

  # A lead left unassigned needs a rule whose only candidate is unavailable.
  # A disposable, already-deactivated agent is that candidate, so AGENT_1 and
  # AGENT_2 — reused across this whole function — never need to be touched.
  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"F3a Temp\",\"email\":\"f3a-temp-$STAMP@x.test\",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  agent_tmp=$(body "$r" | f 'd["id"] or ""')
  check "asesor desechable creado" 201 "$(code "$r")"

  r=$(req -X DELETE "$API/agents/$agent_tmp" -H "Authorization: Bearer $MGR_A")
  check "y desactivado" 200 "$(code "$r")"

  r=$(req -X POST "$API/rules/assignment" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"F3a huérfano\",\"target_agent_ids\":[\"$agent_tmp\"],\"conditions\":[{\"field\":\"custom_attributes.f3a\",\"operator\":\"EQUALS\",\"value\":\"orphan\"}]}")
  check "regla F3a sin candidato disponible" 201 "$(code "$r")"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"F3a","last_name":"Huerfano","company":"Acme","industry":"Retail","budget":1000,"phone":"+573000000011","custom_attributes":{"f3a":"orphan"}}')
  check "el lead huérfano se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead_orphan=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')
  r=$(req "$API/leads/$lead_orphan" -H "Authorization: Bearer $MGR_A")
  check "queda UNASSIGNED" UNASSIGNED "$(body "$r" | f 'd.get("status")')"

  await_notice "$MGR_A" "any(i.get('kind') == 'LEAD_LEFT_UNASSIGNED' and i.get('lead_id') == '$lead_orphan' for i in d.get('items') or [])"
  r=$(req "$API/notifications" -H "Authorization: Bearer $MGR_A")
  check "el gestor recibe LEAD_LEFT_UNASSIGNED" True "$(body "$r" | f 'any(i.get("kind") == "LEAD_LEFT_UNASSIGNED" and i.get("lead_id") == "'"$lead_orphan"'" for i in d.get("items") or [])')"

  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"F3a","last_name":"Rechazo","email":"f3a-bad@@x.test","company":"Acme","industry":"Retail","budget":1000}')
  check "el correo mal formado se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  rec=$(body "$r" | f '(d.get("items") or [{}])[0].get("id") or ""')
  check "y queda REJECTED" REJECTED "$(body "$r" | f '(d.get("items") or [{}])[0].get("status") or ""')"

  await_notice "$MGR_A" "any(i.get('kind') == 'INTAKE_REJECTED' and i.get('intake_record_id') == '$rec' for i in d.get('items') or [])"
  r=$(req "$API/notifications" -H "Authorization: Bearer $MGR_A")
  check "el gestor recibe INTAKE_REJECTED con el registro" True "$(body "$r" | f 'any(i.get("kind") == "INTAKE_REJECTED" and i.get("intake_record_id") == "'"$rec"'" for i in d.get("items") or [])')"

  r=$(req "$API/notifications" -H "Authorization: Bearer $MGR_B")
  check "el gestor de otra organización no ve nada de esto" False "$(body "$r" | f 'any(i.get("lead_id") == "'"$lead_orphan"'" or i.get("intake_record_id") == "'"$rec"'" for i in d.get("items") or [])')"

  # This function runs last, but a manager left with a pile of unread
  # notices is a bad state to hand to whoever extends this file next.
  req -X POST "$API/notifications/read-all" -H "Authorization: Bearer $MGR_A" >/dev/null
}

verify_f31() {
  local r job cutoff lead_id

  section "3.1 · la reobtención"

  # The instant a consumer says it last saw. Ingested before it, so the lead
  # only shows up once something actually moves it.
  r=$(req -X POST "$API/intake/leads/ingest" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"first_name":"Reobtenible","last_name":"Uno","company":"Acme","industry":"Retail","budget":4000,"phone":"+573000000031"}')
  check "el lead se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')
  check "el trabajo termina" COMPLETED "$(await_job "$MGR_A" "$job")"
  r=$(req "$API/intake/records?job_id=$job" -H "Authorization: Bearer $MGR_A")
  lead_id=$(body "$r" | f '(d.get("items") or [{}])[0].get("lead_id") or ""')

  # Slept before reading the clock, not after: `date` truncates to the second,
  # so a lead written 300ms into the same second the cutoff names would fall
  # inside `updated_at >= cutoff` and make this look broken when it is not.
  sleep 1
  cutoff=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  r=$(req "$API/leads?updated_since=$cutoff" -H "Authorization: Bearer $MGR_A")
  check "sin cambios no devuelve nada" 0 "$(body "$r" | f 'd.get("total")')"

  r=$(req -X POST "$API/leads/$lead_id/assign" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"agent_id\":\"$AGENT_1\"}")
  check "el gestor lo asigna a mano" 200 "$(code "$r")"

  r=$(req "$API/leads?updated_since=$cutoff" -H "Authorization: Bearer $MGR_A")
  check "ahora sí aparece en la reobtención" True "$(body "$r" | f 'any(i.get("id") == "'"$lead_id"'" for i in d.get("items") or [])')"

  # The other half of the same requirement: what nobody is working on.
  r=$(req "$API/leads?status=UNASSIGNED" -H "Authorization: Bearer $MGR_A")
  check "y los que no están asignados a nada se listan" 200 "$(code "$r")"
  check "ninguno de ellos tiene asesor" True "$(body "$r" | f 'all(i.get("assigned_agent_id") is None for i in d.get("items") or [])')"

  r=$(req "$API/leads?updated_since=$cutoff" -H "Authorization: Bearer $TOKEN_1")
  check "un asesor no puede reobtener la organización (403)" 403 "$(code "$r")"
}

verify_f41() {
  local r api_key bad_key integration_id

  section "4.1 · la credencial de máquina"

  r=$(req -X POST "$API/agents/integration-credential" -H "Authorization: Bearer $MGR_A")
  check "el gestor emite la credencial" 201 "$(code "$r")"
  api_key=$(body "$r" | f 'd.get("api_key") or ""')
  # Captured from this response, not looked up afterwards: GET /agents no
  # longer lists this row at all (see the check below), so this is the only
  # place the id is ever available over HTTP.
  integration_id=$(body "$r" | f 'd.get("agent_id") or ""')

  r=$(req "$API/leads?updated_since=2020-01-01T00:00:00Z" -H "X-Api-Key: $api_key")
  check "la credencial de máquina lee el propio tenant" 200 "$(code "$r")"

  r=$(req "$API/leads" -H "X-Api-Key: ${api_key}x")
  check "una credencial alterada no autentica" 401 "$(code "$r")"

  r=$(req "$API/leads" -H "Authorization: Bearer $TOKEN_1")
  check "el JWT de un asesor sigue sin poder listar la organización" 403 "$(code "$r")"

  r=$(req "$API/agents?is_active=true" -H "Authorization: Bearer $MGR_A")
  check "la credencial de máquina no aparece en la plantilla del gestor" False \
    "$(body "$r" | f 'any(a.get("role") == "INTEGRATION" for a in d.get("items") or [])')"

  bad_key="$api_key"
  r=$(req -X POST "$API/agents/integration-credential" -H "Authorization: Bearer $MGR_A")
  api_key=$(body "$r" | f 'd.get("api_key") or ""')
  r=$(req "$API/leads" -H "X-Api-Key: $bad_key")
  check "rotar invalida la credencial anterior" 401 "$(code "$r")"
  r=$(req "$API/leads" -H "X-Api-Key: $api_key")
  check "la credencial rotada funciona" 200 "$(code "$r")"

  req -X DELETE "$API/agents/$integration_id" -H "Authorization: Bearer $MGR_A" >/dev/null
  r=$(req "$API/leads" -H "X-Api-Key: $api_key")
  check "revocar corta el acceso" 401 "$(code "$r")"
}

# ------------------------------------------------------------------- F5 ---
# What a real file does to the intake: cells that are empty, cells that carry
# text where a number belongs, and an amount the column cannot hold. Every one
# of these was found by running the demo, and none of them shows up without a
# background task on real HTTP.

verify_f5() {
  local r job record
  section "F5 · un fichero de verdad"

  # pandas reads a blank cell as NaN, and str(NaN) is the word "nan": it used
  # to reach the customer as a company name.
  {
    printf 'first_name,last_name,email,phone,company,budget,industry\n'
    printf 'Ana,Buena,ana-%s@x.test,+34600000001,Buena SL,12000,Tech\n' "$STAMP"
    printf 'Sin,Empresa,sin-%s@x.test,+34600000002,,9000,\n' "$STAMP"
    printf 'Mala,Cifra,mala-%s@x.test,+34600000003,Mala SL,por determinar,Tech\n' "$STAMP"
    printf 'Neg,Ativo,neg-%s@x.test,+34600000004,Neg SL,-500,Tech\n' "$STAMP"
  } > "/tmp/e2e-sucio-$STAMP.csv"

  r=$(req -X POST "$API/intake/leads/batch-upload" -H "Authorization: Bearer $MGR_A" \
    -F "file=@/tmp/e2e-sucio-$STAMP.csv")
  check "el lote se acepta" 202 "$(code "$r")"
  job=$(body "$r" | f 'd.get("job_id") or ""')

  # COMPLETED, never FAILED: one bad cell used to abort the parse, and the use
  # case reads any parse failure as an unreadable file — the two good rows
  # disappeared with the bad ones, without a record left to show for it.
  check "una celda mala no tumba el lote" COMPLETED "$(await_job "$MGR_A" "$job")"

  r=$(req "$API/intake/jobs/$job" -H "Authorization: Bearer $MGR_A")
  check "cuatro filas contadas" 4 "$(body "$r" | f 'd.get("total_items")')"
  check "las dos buenas entran" 2 "$(body "$r" | f 'd.get("succeeded")')"
  check "las dos malas se rechazan, no se pierden" 2 "$(body "$r" | f 'd.get("failed")')"

  r=$(req "$API/intake/records?job_id=$job&limit=50" -H "Authorization: Bearer $MGR_A")
  check "el rechazo nombra el campo" budget \
    "$(body "$r" | f 'next((e["field"] for i in (d.get("items") or []) for e in (i.get("errors") or [])), "")')"

  r=$(req "$API/leads?q=sin-$STAMP&limit=5" -H "Authorization: Bearer $MGR_A")
  check "una celda vacía queda vacía, no dice nan" "" \
    "$(body "$r" | f '(d.get("items") or [{}])[0].get("company")')"

  # The cursor a consumer advances with: filtering by updated_since needs the
  # field to come back, or the client has to guess it from its own clock.
  check "el lead trae su updated_at" True \
    "$(body "$r" | f '(d.get("items") or [{}])[0].get("updated_at") is not None')"

  r=$(req "$API/leads?updated_since=2999-01-01T00:00:00Z" -H "Authorization: Bearer $MGR_A")
  check "updated_since filtra de verdad" 0 "$(body "$r" | f 'd.get("total")')"

  section "F5 · lo que el dominio no llega a ver"

  r=$(req "$API/intake/records?status=REJECTED&job_id=$job&limit=5" -H "Authorization: Bearer $MGR_A")
  record=$(body "$r" | f '(d.get("items") or [{}])[0].get("id") or ""')

  # Above NUMERIC(14,2). Money accepts it, the column does not: untranslated it
  # left as a 500, which a client reads as "retry me" for a value that fails
  # identically on every attempt.
  r=$(req -X POST "$API/intake/records/$record/promote" -H "Authorization: Bearer $MGR_A" \
    -H 'Content-Type: application/json' \
    -d "{\"payload\":{\"first_name\":\"Enorme\",\"last_name\":\"Cifra\",\"email\":\"enorme-$STAMP@x.test\",\"company\":\"X\",\"industry\":\"Tech\",\"budget\":9999999999999}}")
  check "un importe fuera de rango es 400, no 500" 400 "$(code "$r")"
  check "y lleva su código" AMOUNT_OUT_OF_RANGE "$(body "$r" | f 'd.get("error_code")')"

  r=$(req -X POST "$API/intake/records/$record/promote" -H "Authorization: Bearer $MGR_A" \
    -H 'Content-Type: application/json' \
    -d "{\"payload\":{\"first_name\":\"Cifra\",\"last_name\":\"Corregida\",\"email\":\"corregida-$STAMP@x.test\",\"company\":\"X\",\"industry\":\"Tech\",\"budget\":15000}}")
  check "corregido, el registro promociona" 200 "$(code "$r")"

  # Not idempotent here on purpose: a manager asking for something that already
  # happened deserves to be told, and no second lead appears either way.
  r=$(req -X POST "$API/intake/records/$record/promote" -H "Authorization: Bearer $MGR_A" \
    -H 'Content-Type: application/json' \
    -d "{\"payload\":{\"first_name\":\"Cifra\",\"last_name\":\"Corregida\",\"email\":\"corregida-$STAMP@x.test\",\"company\":\"X\",\"industry\":\"Tech\",\"budget\":15000}}")
  check "promocionar dos veces se rechaza" 400 "$(code "$r")"
  check "con la transición nombrada" INVALID_INTAKE_TRANSITION "$(body "$r" | f 'd.get("error_code")')"

  r=$(req "$API/leads?q=corregida-$STAMP&limit=5" -H "Authorization: Bearer $MGR_A")
  check "y no aparece un segundo lead" 1 "$(body "$r" | f 'd.get("total")')"

  rm -f "/tmp/e2e-sucio-$STAMP.csv"
}

# ------------------------------------------------------------- social OAuth ---
# OAuth's real providers must never be part of this harness. A short-lived,
# loopback-only backend gets the explicit test adapter; the normal stack and
# its configuration remain untouched.
verify_social_oauth() {
  local r start_headers jar bad_jar mfa_jar mfa_headers location state port container health secret totp logs
  section "OAuth social · adaptador determinista"

  port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
  container="leads-oauth-e2e-$STAMP"
  docker compose run --no-deps -d --name "$container" -p "127.0.0.1:$port:8000" \
    -e APP_ENV=test -e OAUTH_TEST_MODE=true backend \
    uvicorn infrastructure.main:app --host 0.0.0.0 --port 8000 --app-dir src --no-access-log >/dev/null 2>&1

  health=
  for _ in $(seq 1 30); do
    health=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/health")
    [ "$health" = 200 ] && break
    sleep 0.2
  done
  check "el adaptador OAuth de prueba arranca en loopback" 200 "$health"
  if [ "$health" != 200 ]; then
    docker rm -f "$container" >/dev/null 2>&1 || true
    return
  fi

  start_headers=$(mktemp "/tmp/leads-oauth-e2e-${STAMP}-XXXXXX.headers")
  jar="${start_headers}.cookies"
  r=$(curl -s -D "$start_headers" -o /dev/null -w '%{http_code}' -c "$jar" \
    "http://127.0.0.1:$port/api/v1/auth/oauth/google/start?return_path=/mis-leads")
  location=$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers" | tr -d '\r')
  state=$(oauth_state "$location")
  check "OAuth start responde 303" 303 "$r"
  check "OAuth start deja state y PKCE S256" True "$(printf '%s' "$location" | python3 -c 'import sys; from urllib.parse import parse_qs,urlsplit; q=parse_qs(urlsplit(sys.stdin.read()).query); print(bool(q.get("state")) and q.get("code_challenge_method") == ["S256"])')"
  check "OAuth start fija la cookie de desafío" True "$(grep -qi 'leads_oauth_challenge=.*HttpOnly' "$start_headers" && printf True || printf False)"

  r=$(curl -s -D "$start_headers.callback" -o /dev/null -w '%{http_code}' -b "$jar" -c "$jar" -G \
    --data-urlencode "code=uno-$STAMP@x.test|verified|google-$STAMP" \
    --data-urlencode "state=$state" "http://127.0.0.1:$port/api/v1/auth/oauth/google/callback")
  check "primer callback enlaza al agente existente" 303 "$r"
  check "primer callback crea sesión opaca" True "$(grep -qi 'leads_session=' "$start_headers.callback" && printf True || printf False)"
  check "primer callback vuelve a la ruta interna" "http://localhost/mis-leads" "$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers.callback" | tr -d '\r')"
  r=$(curl -s -o /dev/null -w '%{http_code}' -b "$jar" "http://127.0.0.1:$port/api/v1/auth/me")
  check "la sesión social rehidrata al agente enlazado" 200 "$r"

  r=$(curl -s -o /dev/null -w '%{http_code}' -b "$jar" -X POST "http://127.0.0.1:$port/api/v1/auth/logout")
  check "la sesión social se puede cerrar" 204 "$r"
  r=$(curl -s -D "$start_headers.repeat" -o /dev/null -w '%{http_code}' -b "$jar" -c "$jar" \
    "http://127.0.0.1:$port/api/v1/auth/oauth/google/start?return_path=/mis-leads")
  state=$(oauth_state "$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers.repeat" | tr -d '\r')")
  r=$(curl -s -D "$start_headers.repeat.callback" -o /dev/null -w '%{http_code}' -b "$jar" -c "$jar" -G \
    --data-urlencode "code=uno-$STAMP@x.test|verified|google-$STAMP" \
    --data-urlencode "state=$state" "http://127.0.0.1:$port/api/v1/auth/oauth/google/callback")
  check "el subject repetido inicia de nuevo" 303 "$r"

  bad_jar=$(mktemp "/tmp/leads-oauth-e2e-${STAMP}-XXXXXX.cookies")
  r=$(curl -s -D "$start_headers.bad" -o /dev/null -w '%{http_code}' -c "$bad_jar" \
    "http://127.0.0.1:$port/api/v1/auth/oauth/google/start")
  state=$(oauth_state "$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers.bad" | tr -d '\r')")
  r=$(curl -s -D "$start_headers.bad.callback" -o /dev/null -w '%{http_code}' -b "$bad_jar" -G \
    --data-urlencode "code=uno-$STAMP@x.test|unverified|unverified-$STAMP" \
    --data-urlencode "state=$state" "http://127.0.0.1:$port/api/v1/auth/oauth/google/callback")
  check "un correo sin verificar vuelve al error genérico" "http://localhost/login?oauth_error=1" "$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers.bad.callback" | tr -d '\r')"
  check "un correo sin verificar no fija sesión" False "$(grep -qi 'leads_session=' "$start_headers.bad.callback" && printf True || printf False)"

  mfa_jar=$(login "dos-$STAMP@x.test" "$ADMIN_PASS")
  secret=$(curl -s -b "$mfa_jar" -H 'Content-Type: application/json' -d "{\"password\":\"$ADMIN_PASS\"}" "$API/auth/mfa/setup" | f 'd.get("secret") or ""')
  totp=$(python3 - "$secret" <<'PY'
import base64, hashlib, hmac, struct, sys, time
key = base64.b32decode(sys.argv[1], casefold=True)
counter = struct.pack(">Q", int(time.time()) // 30)
digest = hmac.new(key, counter, hashlib.sha1).digest()
offset = digest[-1] & 15
value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff) % 1000000
print(f"{value:06d}")
PY
)
  r=$(curl -s -o /dev/null -w '%{http_code}' -b "$mfa_jar" -H 'Content-Type: application/json' \
    -d "{\"code\":\"$totp\"}" "$API/auth/mfa/setup/confirm")
  check "el agente de la transición OAuth tiene MFA activo" 200 "$r"

  r=$(curl -s -D "$start_headers.mfa" -o /dev/null -w '%{http_code}' -c "$mfa_jar" \
    "http://127.0.0.1:$port/api/v1/auth/oauth/google/start")
  state=$(oauth_state "$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers.mfa" | tr -d '\r')")
  r=$(curl -s -D "$start_headers.mfa.callback" -o /dev/null -w '%{http_code}' -b "$mfa_jar" -c "$mfa_jar" -G \
    --data-urlencode "code=dos-$STAMP@x.test|verified|mfa-google-$STAMP" \
    --data-urlencode "state=$state" "http://127.0.0.1:$port/api/v1/auth/oauth/google/callback")
  check "OAuth con MFA redirige al desafío" "http://localhost/mfa" "$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers.mfa.callback" | tr -d '\r')"
  check "OAuth con MFA revoca la sesión previa y fija el desafío temporal" True "$(grep -qi 'leads_mfa_challenge=' "$start_headers.mfa.callback" && grep -qi 'leads_session=.*max-age=0' "$start_headers.mfa.callback" && printf True || printf False)"
  r=$(curl -s -D "$start_headers.replay" -o /dev/null -w '%{http_code}' -b "$mfa_jar" -G \
    --data-urlencode "code=dos-$STAMP@x.test|verified|mfa-google-$STAMP" \
    --data-urlencode "state=$state" "http://127.0.0.1:$port/api/v1/auth/oauth/google/callback")
  check "un callback OAuth repetido se rechaza" "http://localhost/login?oauth_error=1" "$(awk 'tolower($1) == "location:" { print $2 }' "$start_headers.replay" | tr -d '\r')"

  logs=$(docker logs "$container" 2>&1)
  check "el adaptador no deja tracebacks ni datos OAuth en logs" False "$(printf '%s' "$logs" | grep -Eqi 'traceback|google-[0-9]|mfa-google-[0-9]|unverified-[0-9]' && printf True || printf False)"
  docker rm -f "$container" >/dev/null 2>&1 || true
  rm -f "$start_headers" "$start_headers".* "$jar" "$bad_jar" "$mfa_jar"
}


# ------------------------------------------------ microservicios · F0 ---
# Gateway and phantom token (ADR-0032): what the edge guarantees and what the
# service still enforces on its own. Runs last: it stops the backend.
verify_ms_f0() {
  local r headers base mgr_a_id forged key status i
  section "Microservicios F0 · gateway y phantom token"
  base=${API%/api/v1}
  headers=$(mktemp "/tmp/leads-e2e-${STAMP}-XXXXXX.headers")

  r=$(req "$API/leads" -H "Authorization: Bearer not-a-jwt")
  check "bearer basura sin cookie → 401" 401 "$(code "$r")"
  check "401 con el sobre de siempre" UNAUTHORIZED "$(body "$r" | f 'd["error_code"] if d.get("error") is True else ""')"
  check "401 con el mensaje del gateway" "Authentication required" "$(body "$r" | f 'd["message"]')"

  mgr_a_id=$(body "$(req "$API/auth/me" -H "Authorization: Bearer $MGR_A")" | f 'd["id"]')
  forged=$(docker compose exec -T backend python -c '
import sys, time, uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from chassis.auth import Ed25519Signer
now = int(time.time())
print(Ed25519Signer("dev-1", Ed25519PrivateKey.generate()).sign({"iss": "identity", "aud": "lead-router",
    "sub": sys.argv[1], "tid": sys.argv[2], "role": "MANAGER", "ptype": "human",
    "iat": now, "exp": now + 60, "jti": str(uuid.uuid4())}))' "$mgr_a_id" "$TENANT_A")
  # An empty $forged (the exec failed) would let the three checks below pass for the wrong reason.
  check "JWT forjado generado" 3 "$(printf '%s' "$forged" | awk -F. '{print NF}')"
  r=$(req "$API/leads" -H "Authorization: Bearer $forged")
  check "JWT de otra clave por el gateway → 401" 401 "$(code "$r")"
  status=$(docker compose exec -T backend python -c '
import sys, urllib.request, urllib.error
req = urllib.request.Request("http://localhost:8000/api/v1/leads", headers={"Authorization": "Bearer " + sys.argv[1]})
try:
    print(urllib.request.urlopen(req).status)
except urllib.error.HTTPError as e:
    print(e.code)' "$forged")
  check "JWT de otra clave directo al servicio → 401" 401 "$status"
  r=$(req "$API/leads" -H "Authorization: Bearer $TOKEN_1" -H "Authorization: Bearer $forged")
  check "el Authorization del cliente no llega: manda la cookie" 403 "$(code "$r")"

  check "jwks no se publica" 404 "$(code "$(req "$base/internal/v1/jwks")")"
  check "introspect no se publica" 404 "$(code "$(req "$base/internal/v1/auth/introspect")")"

  curl -s -o /dev/null -D "$headers" -H "X-Request-Id: e2e-$STAMP" "$API/auth/me"
  check "X-Request-Id entrante se conserva" "e2e-$STAMP" "$(awk 'tolower($1)=="x-request-id:"{print $2}' "$headers" | tr -d '\r')"
  curl -s -o /dev/null -D "$headers" "$API/auth/me"
  check "X-Request-Id se genera si falta" True "$(awk 'tolower($1)=="x-request-id:"{print $2}' "$headers" | tr -d '\r' | grep -qE '^[A-Za-z0-9]{16,}$' && printf True || printf False)"
  curl -s -o /dev/null -D "$headers" -H "X-Request-Id: no vale;$STAMP" "$API/auth/me"
  check "X-Request-Id hostil se sustituye" False "$(grep -qi "no vale" "$headers" && printf True || printf False)"
  curl -s -o /dev/null -D "$headers" -H "X-Request-Id: $(head -c 129 /dev/zero | tr '\0' a)" "$API/auth/me"
  check "X-Request-Id de 129 caracteres se sustituye" False "$(grep -qE '^[Xx]-[Rr]equest-[Ii]d: a{129}' "$headers" && printf True || printf False)"
  check "el access log del gateway lleva el id" True "$(docker compose logs --since 2m gateway | grep -q "rid=e2e-$STAMP" && printf True || printf False)"

  r=$(curl -s -o /dev/null -D "$headers" -w '%{http_code}' -X OPTIONS "$API/auth/login" \
    -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: POST")
  check "preflight de origen permitido" 204 "$r"
  check "preflight devuelve el origen" "http://localhost:5173" "$(awk 'tolower($1)=="access-control-allow-origin:"{print $2}' "$headers" | tr -d '\r')"
  check "preflight permite credenciales" true "$(awk 'tolower($1)=="access-control-allow-credentials:"{print $2}' "$headers" | tr -d '\r')"
  r=$(curl -s -o /dev/null -D "$headers" -w '%{http_code}' -X POST "$API/auth/login" \
    -H "Origin: http://localhost:5173.evil.test" --data-urlencode "username=mgr-b-$STAMP@x.test" --data-urlencode "password=$ADMIN_PASS")
  check "dominio parecido no es origen permitido" 403 "$r"
  check "un Origin hostil no crea sesión" False "$(grep -qi 'set-cookie: leads_session' "$headers" && printf True || printf False)"
  r=$(curl -s -o /dev/null -D "$headers" -w '%{http_code}' -X POST "$API/auth/login" \
    -H "Origin: http://localhost" --data-urlencode "username=mgr-b-$STAMP@x.test" --data-urlencode "password=$ADMIN_PASS")
  check "login con origen permitido" 200 "$r"
  check "y fija la sesión" True "$(grep -qi 'set-cookie: leads_session' "$headers" && printf True || printf False)"
  r=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/auth/login" -H "Referer: https://evil.test/" \
    --data-urlencode "username=mgr-b-$STAMP@x.test" --data-urlencode "password=$ADMIN_PASS")
  check "un Referer hostil sin Origin no cuenta" 200 "$r"
  r=$(req -X POST "$API/rules/scoring" -H "X-Api-Key: not-a-real-key" -H "Origin: https://evil.test" \
    -H 'Content-Type: application/json' -d '{"name":"X","conditions":[],"score_delta":1}')
  check "X-Api-Key con Origin hostil → 403 antes de autenticar" 403 "$(code "$r")"

  r=$(req -X POST "$API/agents/integration-credential" -H "Authorization: Bearer $MGR_B")
  key=$(body "$r" | f 'd.get("api_key") or ""')
  check "X-Api-Key válida en GET /leads" 200 "$(code "$(req "$API/leads" -H "X-Api-Key: $key")")"
  check "X-Api-Key válida fuera de GET /leads → 401" 401 "$(code "$(req "$API/rules/scoring" -H "X-Api-Key: $key")")"

  r=$(req -X POST "$API/agents/" -H 'Content-Type: application/json' \
    -d '{"name":"X","email":"x@x.test","password":"Secret123","role":"ADMIN"}')
  check "POST /agents anónimo con agentes ya creados → 401" 401 "$(code "$r")"

  head -c 11000000 /dev/zero > "$headers.big"
  r=$(req -X POST "$API/intake/leads/batch-upload" -H "Authorization: Bearer $MGR_A" -F "file=@$headers.big;filename=big.csv")
  check "cuerpo mayor de 10 MB → 413" 413 "$(code "$r")"

  docker compose stop backend >/dev/null 2>&1
  r=$(req "$API/leads" -H "Authorization: Bearer $MGR_A")
  check "identity caída → 503 (siempre cerrado)" 503 "$(code "$r")"
  check "503 con sobre" SERVICE_UNAVAILABLE "$(body "$r" | f 'd.get("error_code")')"
  docker compose start backend >/dev/null 2>&1
  for i in $(seq 1 60); do
    [ "$(code "$(req "$API/auth/me")")" = 401 ] && break
    sleep 1
  done
  check "el backend vuelve tras el corte" 200 "$(code "$(req "$API/leads" -H "Authorization: Bearer $MGR_A")")"
  rm -f "$headers" "$headers.big"
}


# ------------------------------------------------------------------- main ---

if [ "${1:-}" = "--reset" ]; then
  printf 'Recreando el volumen…\n'
  docker compose down -v >/dev/null 2>&1
  docker compose up -d >/dev/null 2>&1
  # The gateway answers /health before the backend has migrated; /auth/me
  # reaches the backend and only returns 401 once it is serving.
  for _ in $(seq 1 60); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' "$API/auth/me")" = 401 ] && break
    sleep 1
  done
fi

bootstrap
verify_sessions
verify_f0_identity
verify_f2a
verify_f2b
verify_f2d
verify_f2c
verify_f3a
verify_f31
verify_f41
verify_f5
verify_social_oauth
verify_ms_f0

printf '\n'
if [ "$FAILURES" -eq 0 ]; then
  printf '\033[32mTodo verde.\033[0m\n'
else
  printf '\033[31m%s comprobaciones fallaron.\033[0m\n' "$FAILURES"
fi
exit "$FAILURES"
