from tests.e2e.helpers.auth_helpers import seed_org_manager
from tests.e2e.helpers.gateway_client import GatewayClient

from infrastructure.main import app


def _manager(client: GatewayClient) -> dict:
    return seed_org_manager()


def test_a_list_valued_rule_survives_the_round_trip(test_db):
    """The IN operator never fired because value was coerced to str."""
    with GatewayClient(app) as client:
        manager = _manager(client)
        created = client.post(
            "/api/v1/rules/scoring",
            headers=manager,
            json={
                "name": "Sectores objetivo",
                "conditions": [{"field": "industry", "operator": "IN", "value": ["tech", "finance"]}],
                "score_delta": 40,
            },
        )
        assert created.status_code == 201

        listed = client.get(
            "/api/v1/rules/scoring", headers=manager
        )
        rule = next(r for r in listed.json()["items"] if r["name"] == "Sectores objetivo")
        assert rule["conditions"][0]["value"] == ["tech", "finance"]


def test_a_numeric_rule_keeps_its_number(test_db):
    with GatewayClient(app) as client:
        manager = _manager(client)
        created = client.post(
            "/api/v1/rules/scoring",
            headers=manager,
            json={
                "name": "Presupuesto alto",
                "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 5000}],
                "score_delta": 30,
            },
        )
        assert created.status_code == 201
        assert created.json()["conditions"][0]["value"] == 5000


def test_a_field_outside_the_allow_list_is_refused(test_db):
    with GatewayClient(app) as client:
        manager = _manager(client)
        refused = client.post(
            "/api/v1/rules/scoring",
            headers=manager,
            json={
                "name": "Fuga",
                "conditions": [{"field": "tenant_id", "operator": "EQUALS", "value": "x"}],
                "score_delta": 10,
            },
        )
        assert refused.status_code == 400
        assert refused.json()["error_code"] == "FIELD_NOT_SCORABLE"
