"""Contract test: nothing sent to the API is ever discarded on the way out.

Four times already a field declared in a Pydantic schema (`email`, `source_id`,
`intake_record_id`, `disqualification_reason`) reached the API contract while
the router never filled it, and no existing test caught it — status-code and
storage assertions do not read the whole response body.

This file runs two complementary checks per entity:

1. `assert_round_trip` — send a value for every optional field, reread the
   entity, and confirm what comes back is what was sent. Catches the router
   that forgets to fill a field.
2. The `NULLABLE_BY_DESIGN` walk — recurse every field the Pydantic model
   declares and fail if it is `None` and not listed as legitimately nullable.
   Catches the field the schema declares that no router ever fills.

When this test goes red, the fix is filling the field in the router — never
widening `NULLABLE_BY_DESIGN`. An entry there needs a reason; a reason-less
entry is exactly how the fifth case gets back in.
"""
import uuid

from gateway_client import GatewayClient

from infrastructure.main import app
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.input.api import schemas

from _intake_helpers import ingest_and_resolve
from auth_helpers import manager_headers, seed_agent


# --- Auth / seeding helpers, same shortcuts as test_lead_endpoints.py ---

def _manager_auth_headers(tenant_id: str) -> dict:
    return manager_headers(tenant_id)


def _seed_tenant_with_sources(tenant_id: str) -> None:
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from domain.entities.lead_source import LeadSource

    uow = PostgresUnitOfWork(app.state.container.database)
    with uow:
        uow.sources.save(
            LeadSource.create(tenant_id=tenant_id, name="Formulario manual", kind=LeadSourceKind.MANUAL_FORM)
        )


# --- Comprobación 1: nothing sent comes back empty ---

def assert_round_trip(sent: dict, received: dict, *, aliases: dict[str, str] | None = None) -> None:
    """Every value sent must come back. A None or a missing key means the
    adapter dropped a field on its way out."""
    for key, value in sent.items():
        name = (aliases or {}).get(key, key)
        assert name in received, f"{name} no aparece en la respuesta"
        assert received[name] is not None, f"{name} vuelve vacío pese a haberse enviado"
        if isinstance(value, (str, int, bool)) and not isinstance(value, dict):
            assert received[name] == value, f"{name}: se envió {value!r}, volvió {received[name]!r}"


# --- Comprobación 2: no schema field is silently unfillable ---

# Fields that legitimately come back None, with the reason each is there.
# A field missing here that returns None makes the test fail on purpose —
# that failure is fixed in the router, never by adding a line below it.
NULLABLE_BY_DESIGN: dict[str, set[str]] = {
    "LeadDetailResponse": {
        # Mutually exclusive lifecycle states of a single lead: a freshly
        # ingested lead is none of these yet. Each is exercised directly
        # against its own transition below (assign / discard / disqualify)
        # rather than all at once, which no single lead can be.
        "assigned_agent_id",
        "assigned_at",
        "discard_reason",
        "disqualification_reason",
    },
    "IntakeRecordResponse": {
        # Only a PROMOTED record produced a lead; the REJECTED record this
        # test creates never did (ADR-driven: rejection keeps the payload
        # visible in the tray instead of silently discarding it).
        "lead_id",
    },
}


def assert_schema_fields_filled(model_cls, received: dict) -> None:
    name = model_cls.__name__
    nullable = NULLABLE_BY_DESIGN.get(name, set())
    for field_name in model_cls.model_fields:
        if field_name in nullable:
            continue
        assert field_name in received, f"{name}.{field_name} no aparece en la respuesta"
        assert received[field_name] is not None, (
            f"{name}.{field_name} vuelve None y no está en NULLABLE_BY_DESIGN[{name!r}]"
        )


_FORBIDDEN_SUBSTRINGS = ("hashed_password", "secret_hash", "password")


def assert_no_credentials_leaked(response) -> None:
    body = response.text.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in body, f"la respuesta filtra '{forbidden}'"


# --- Lead: covered first and with the widest payload, per the task's own history ---

def test_lead_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        payload = {
            "first_name": "Maria",
            "last_name": "Gomez",
            "email": "mgomez@contract.test",
            "company": "ContractCo",
            "budget": 15000.0,
            "industry": "Technology",
            "custom_attributes": {"employee_count": 150},
            "phone": "+525551234567",
        }
        record = ingest_and_resolve(client, headers, payload)
        assert record["status"] in ("PROMOTED",), record

        resp = client.get(f"/api/v1/leads/{record['lead_id']}", headers=headers)
        assert resp.status_code == 200, resp.text
        assert_no_credentials_leaked(resp)
        data = resp.json()

        assert_round_trip(payload, data)
        assert data["id"] == record["lead_id"]
        assert data["tenant_id"] == tenant_id
        assert data["source_id"]
        assert_schema_fields_filled(schemas.LeadDetailResponse, data)


def test_lead_assigned_agent_id_and_assigned_at_get_filled_when_assigned():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        _, agent_id = seed_agent(tenant_id, "Agent")

        record = ingest_and_resolve(client, headers, {
            "first_name": "Ana", "last_name": "Soto", "email": "ana@assign.test",
            "company": "AssignCo", "budget": 1000.0, "industry": "Tech",
        })
        resp = client.post(
            f"/api/v1/leads/{record['lead_id']}/assign", json={"agent_id": agent_id}, headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["assigned_agent_id"] == agent_id
        assert data["assigned_at"] is not None


def test_lead_discard_reason_gets_filled_when_discarded():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        record = ingest_and_resolve(client, headers, {
            "first_name": "Bea", "last_name": "Ruiz", "email": "bea@discard.test",
            "company": "DiscardCo", "budget": 1000.0, "industry": "Tech",
        })
        resp = client.post(
            f"/api/v1/leads/{record['lead_id']}/discard",
            json={"reason": "No cumple criterios"}, headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["discard_reason"] == "No cumple criterios"


def test_lead_disqualification_reason_gets_filled_when_a_rule_disqualifies_it():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        rule_resp = client.post(
            "/api/v1/rules/disqualification",
            json={
                "name": "Sin presupuesto viable",
                "conditions": [{"field": "industry", "operator": "EQUALS", "value": "Disqualified"}],
                "priority": 0,
                "is_active": True,
            },
            headers=headers,
        )
        assert rule_resp.status_code == 201, rule_resp.text

        record = ingest_and_resolve(client, headers, {
            "first_name": "Cid", "last_name": "Vera", "email": "cid@disqualify.test",
            "company": "DisqualifyCo", "budget": 1000.0, "industry": "Disqualified",
        })
        assert record["status"] == "PROMOTED"

        resp = client.get(f"/api/v1/leads/{record['lead_id']}", headers=headers)
        data = resp.json()
        assert data["status"] == "DISQUALIFIED"
        assert data["disqualification_reason"] is not None


# --- Intake record: created REJECTED, so its per-field error tray is exercised ---

def test_intake_record_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        bad_payload = {
            "first_name": "Mal", "last_name": "Formado", "email": "sin-arroba",
            "company": "BadCo", "budget": 1000.0, "industry": "Tech",
        }
        accepted = client.post("/api/v1/intake/leads/ingest", json=bad_payload, headers=headers)
        assert accepted.status_code == 202, accepted.text
        job_id = accepted.json()["job_id"]

        resp = client.get(f"/api/v1/intake/records?job_id={job_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        assert_no_credentials_leaked(resp)
        items = resp.json()["items"]
        assert len(items) == 1
        data = items[0]

        assert data["status"] == "REJECTED"
        # The stored payload carries the request's defaults too
        # (custom_attributes, phone), not just what the test sent.
        assert data["payload"].items() >= bad_payload.items()
        assert data["errors"], "un registro rechazado debe traer al menos un error"
        assert_schema_fields_filled(schemas.IntakeRecordResponse, data)


# --- Intake job ---

def test_intake_job_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        accepted = client.post(
            "/api/v1/intake/leads/ingest",
            json={
                "first_name": "Dan", "last_name": "Solis", "email": "dan@job.test",
                "company": "JobCo", "budget": 1000.0, "industry": "Tech",
            },
            headers=headers,
        )
        assert accepted.status_code == 202, accepted.text
        job_id = accepted.json()["job_id"]

        resp = client.get(f"/api/v1/intake/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        assert_no_credentials_leaked(resp)
        data = resp.json()

        assert data["id"] == job_id
        assert data["status"] == "COMPLETED"
        assert_schema_fields_filled(schemas.IntakeJobResponse, data)


# --- Sales group ---

def test_group_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        payload = {
            "name": "Sales Team",
            "description": "El equipo de ventas del norte",
            "default_strategy": "ROUND_ROBIN",
            "capacity_per_agent": 10,
        }
        create_resp = client.post("/api/v1/groups", json=payload, headers=headers)
        assert create_resp.status_code == 201, create_resp.text
        group_id = create_resp.json()["id"]

        resp = client.get("/api/v1/groups", headers=headers)
        assert resp.status_code == 200, resp.text
        data = next(item for item in resp.json()["items"] if item["id"] == group_id)

        assert_round_trip(
            {"name": payload["name"], "description": payload["description"],
             "capacity_per_agent": payload["capacity_per_agent"]},
            data,
        )
        assert data["default_strategy"] == payload["default_strategy"]
        assert_schema_fields_filled(schemas.SalesGroupResponse, data)


# --- Lead source ---

def test_source_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        payload = {
            "name": "Formulario web",
            "kind": "MANUAL_FORM",
            "field_mapping": {"nombre": "first_name", "correo": "email"},
        }
        create_resp = client.post("/api/v1/sources", json=payload, headers=headers)
        assert create_resp.status_code == 201, create_resp.text
        source_id = create_resp.json()["id"]

        resp = client.get("/api/v1/sources", headers=headers)
        assert resp.status_code == 200, resp.text
        data = next(item for item in resp.json()["items"] if item["id"] == source_id)

        assert_round_trip({"name": payload["name"], "field_mapping": payload["field_mapping"]}, data)
        assert data["kind"] == payload["kind"]
        assert_schema_fields_filled(schemas.LeadSourceResponse, data)


# --- Assignment rule ---

def test_assignment_rule_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        group_resp = client.post("/api/v1/groups", json={"name": "Target Group"}, headers=headers)
        group_id = group_resp.json()["id"]

        _, agent_id = seed_agent(tenant_id, "Target Agent", group_id)

        payload = {
            "name": "High score to group",
            "min_score": 10,
            "max_score": 100,
            "target_group_id": group_id,
            "target_agent_ids": [agent_id],
            "agent_match_mode": "ANY",
            "strategy": "LOWEST_LOAD",
            "priority": 1,
            "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 500}],
        }
        create_resp = client.post("/api/v1/rules/assignment", json=payload, headers=headers)
        assert create_resp.status_code == 201, create_resp.text
        rule_id = create_resp.json()["id"]

        resp = client.get("/api/v1/rules/assignment", headers=headers)
        assert resp.status_code == 200, resp.text
        data = next(item for item in resp.json()["items"] if item["id"] == rule_id)

        assert_round_trip(
            {"name": payload["name"], "min_score": payload["min_score"], "max_score": payload["max_score"],
             "target_group_id": payload["target_group_id"], "agent_match_mode": payload["agent_match_mode"],
             "strategy": payload["strategy"], "priority": payload["priority"]},
            data,
        )
        assert data["target_agent_ids"] == payload["target_agent_ids"]
        assert data["conditions"]
        assert_schema_fields_filled(schemas.AssignmentRuleResponse, data)


# --- Scoring rule ---

def test_scoring_rule_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        payload = {
            "name": "Big budget bonus",
            "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 1000}],
            "score_delta": 20,
            "priority": 2,
            "is_active": True,
        }
        create_resp = client.post("/api/v1/rules/scoring", json=payload, headers=headers)
        assert create_resp.status_code == 201, create_resp.text
        rule_id = create_resp.json()["id"]

        resp = client.get("/api/v1/rules/scoring", headers=headers)
        assert resp.status_code == 200, resp.text
        data = next(item for item in resp.json()["items"] if item["id"] == rule_id)

        assert_round_trip(
            {"name": payload["name"], "score_delta": payload["score_delta"],
             "priority": payload["priority"], "is_active": payload["is_active"]},
            data,
        )
        assert data["conditions"]
        assert_schema_fields_filled(schemas.ScoringRuleResponse, data)


# --- Disqualification rule ---

def test_disqualification_rule_round_trip_and_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        payload = {
            "name": "No industry match",
            "conditions": [{"field": "industry", "operator": "EQUALS", "value": "Banned"}],
            "priority": 3,
            "is_active": True,
        }
        create_resp = client.post("/api/v1/rules/disqualification", json=payload, headers=headers)
        assert create_resp.status_code == 201, create_resp.text
        rule_id = create_resp.json()["id"]

        resp = client.get("/api/v1/rules/disqualification", headers=headers)
        assert resp.status_code == 200, resp.text
        data = next(item for item in resp.json()["items"] if item["id"] == rule_id)

        assert_round_trip(
            {"name": payload["name"], "priority": payload["priority"], "is_active": payload["is_active"]},
            data,
        )
        assert data["conditions"]
        assert_schema_fields_filled(schemas.DisqualificationRuleResponse, data)


# --- Lead stats: not an entity, but its own contract worth pinning down ---

def test_lead_stats_schema_contract():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        ingest_and_resolve(client, headers, {
            "first_name": "Fay", "last_name": "Ortiz", "email": "fay@stats.test",
            "company": "StatsCo", "budget": 1000.0, "industry": "Tech",
        })

        resp = client.get("/api/v1/leads/stats", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # The promise this test exists to pin down: all six statuses are
        # always present, zero where empty, never a missing key.
        assert set(data["by_status"].keys()) == {
            "NEW", "QUALIFIED", "DISQUALIFIED", "UNASSIGNED", "ASSIGNED", "DISCARDED",
        }
        assert_schema_fields_filled(schemas.LeadStatsResponse, data)
