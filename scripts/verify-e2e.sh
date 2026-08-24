#!/usr/bin/env bash
#
# End-to-end business verification against a running stack.
#
# This is the trust harness: it asserts what the pytest suite cannot, namely
# that the whole circuit behaves over real HTTP with real tokens. It is meant to
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

req() { curl -s -w '\n%{http_code}' "$@"; }
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

login() {
  curl -s -X POST "$API/auth/login" -d "username=$1&password=$2" |
    python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))'
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

# await_job <token> <job_id> — waits until a job reaches a terminal status.
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
  [ -n "$ADMIN_TOKEN" ] || { printf '  \033[31m✗ sin token de admin: abortando\033[0m\n'; exit 1; }

  r=$(req -X POST "$API/tenants" -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
    -d "{\"name\":\"OrgA-$STAMP\",\"manager\":{\"name\":\"MgrA\",\"email\":\"mgr-a-$STAMP@x.test\",\"password\":\"$ADMIN_PASS\"}}")
  check "organización A creada" 201 "$(code "$r")"
  TENANT_A=$(body "$r" | f 'd["id"]')
  MGR_A=$(login "mgr-a-$STAMP@x.test" "$ADMIN_PASS")

  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Uno\",\"email\":\"uno-$STAMP@x.test\",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  AGENT_1=$(body "$r" | f 'd["id"]')
  check "asesor uno" 201 "$(code "$r")"

  r=$(req -X POST "$API/agents/" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d "{\"name\":\"Dos\",\"email\":\"dos-$STAMP@x.test\",\"password\":\"$ADMIN_PASS\",\"role\":\"AGENT\"}")
  AGENT_2=$(body "$r" | f 'd["id"]')
  check "asesor dos" 201 "$(code "$r")"

  TOKEN_1=$(login "uno-$STAMP@x.test" "$ADMIN_PASS")
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

# ------------------------------------------------------------------- main ---

if [ "${1:-}" = "--reset" ]; then
  printf 'Recreando el volumen…\n'
  docker compose down -v >/dev/null 2>&1
  docker compose up -d >/dev/null 2>&1
  # The API needs the migrations applied before it answers.
  for _ in $(seq 1 30); do
    curl -sf "${API%/api/v1}/health" >/dev/null 2>&1 && break
    sleep 1
  done
fi

bootstrap
verify_f2a
verify_f2b
verify_f2d
verify_f2c
verify_f3a
verify_f31

printf '\n'
if [ "$FAILURES" -eq 0 ]; then
  printf '\033[32mTodo verde.\033[0m\n'
else
  printf '\033[31m%s comprobaciones fallaron.\033[0m\n' "$FAILURES"
fi
exit "$FAILURES"
