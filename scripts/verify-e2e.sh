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
  local r
  section "F2a · reglas de puntuación"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"tech o saas","field":"industry","operator":"IN","value":["Tech","SaaS"],"score_delta":40,"priority":10}')
  check "IN acepta una lista" 201 "$(code "$r")"
  check "IN la almacena como lista, no como texto" "['Tech', 'SaaS']" "$(body "$r" | f 'd["value"]')"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"presupuesto alto","field":"budget","operator":"GREATER_THAN","value":5000,"score_delta":25,"priority":5}')
  check "GREATER_THAN conserva el número" 5000 "$(body "$r" | f 'd["value"]')"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"inactiva","field":"company","operator":"EQUALS","value":"Acme","score_delta":99,"is_active":false}')
  check "regla inactiva se acepta" 201 "$(code "$r")"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"no puntuable","field":"tenant_id","operator":"EQUALS","value":"x","score_delta":10}')
  check "un campo interno no es puntuable" FIELD_NOT_SCORABLE "$(body "$r" | f 'd.get("error_code")')"

  r=$(req -X POST "$API/rules/scoring" -H "Authorization: Bearer $MGR_A" -H 'Content-Type: application/json' \
    -d '{"name":"IN mal","field":"industry","operator":"IN","value":"Tech","score_delta":10}')
  check "IN exige una lista" INVALID_RULE_VALUE "$(body "$r" | f 'd.get("error_code")')"

  section "F2a · ingesta sin regla de asignación"

  r=$(req -X POST "$API/intake/$TENANT_A/leads/ingest" -H 'Content-Type: application/json' \
    -d '{"first_name":"Ana","last_name":"Diaz","email":"ana@lead.test","company":"Acme","industry":"Tech","budget":9000}')
  check "el lead entra" 201 "$(code "$r")"
  check "sin asesor queda UNASSIGNED" UNASSIGNED "$(body "$r" | f 'd.get("status")')"
  check "puntúa 40+25 y la inactiva no cuenta" 65 "$(body "$r" | f 'd.get("score")')"
  check "applied_rules_count es real" 2 "$(body "$r" | f 'd.get("applied_rules_count")')"
  LEAD=$(body "$r" | f 'd["lead_id"]')

  r=$(req "$API/leads/$LEAD" -H "Authorization: Bearer $MGR_A")
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

# ---------------------------------------------------------------- next up ---
# verify_f2b()  ingesta unificada: nada se pierde, nadie ingesta sin credencial
# verify_f2c()  reglas componibles: descalificación con motivo, reparto por canal

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

printf '\n'
if [ "$FAILURES" -eq 0 ]; then
  printf '\033[32mTodo verde.\033[0m\n'
else
  printf '\033[31m%s comprobaciones fallaron.\033[0m\n' "$FAILURES"
fi
exit "$FAILURES"
