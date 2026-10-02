from auth_helpers import admin_headers, agent_of, seed_org_manager
from gateway_client import GatewayClient

from infrastructure.main import app


def _bootstrap_admin_headers(client: GatewayClient) -> dict:
    """The platform ADMIN; organizations are identity's, so it only names the caller now."""
    return admin_headers()


def _create_org_manager_headers(client: GatewayClient, admin_headers: dict) -> dict:
    """The manager of a fresh organization."""
    return seed_org_manager()


def _agent_headers(client: GatewayClient, manager_headers: dict) -> dict:
    """A plain AGENT inside the manager's organization."""
    return agent_of(manager_headers)[0]


def _budget_rule_payload(name: str = "Presupuesto alto") -> dict:
    return {
        "name": name,
        "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
        "score_delta": 25,
    }


def test_patch_with_only_is_active_keeps_name_and_conditions():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload(), headers=manager_headers
        )
        assert created.status_code == 201, created.text
        rule_id = created.json()["id"]

        updated = client.patch(
            f"/api/v1/rules/scoring/{rule_id}",
            json={"is_active": False},
            headers=manager_headers,
        )
        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["is_active"] is False
        assert body["name"] == "Presupuesto alto"
        assert body["conditions"] == created.json()["conditions"]


def test_patch_of_another_organizations_rule_returns_404_not_403():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_a_headers = _create_org_manager_headers(client, admin_headers)
        manager_b_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload(), headers=manager_a_headers
        )
        assert created.status_code == 201, created.text
        foreign_rule_id = created.json()["id"]

        response = client.patch(
            f"/api/v1/rules/scoring/{foreign_rule_id}",
            json={"is_active": False},
            headers=manager_b_headers,
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "SCORING_RULE_NOT_FOUND"


def test_delete_removes_rule_from_listing():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload(), headers=manager_headers
        )
        assert created.status_code == 201, created.text
        rule_id = created.json()["id"]

        deleted = client.delete(f"/api/v1/rules/scoring/{rule_id}", headers=manager_headers)
        assert deleted.status_code == 204, deleted.text

        listing = client.get("/api/v1/rules/scoring", headers=manager_headers)
        assert rule_id not in {item["id"] for item in listing.json()["items"]}


def test_delete_of_another_organizations_rule_returns_404():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_a_headers = _create_org_manager_headers(client, admin_headers)
        manager_b_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload(), headers=manager_a_headers
        )
        assert created.status_code == 201, created.text
        foreign_rule_id = created.json()["id"]

        response = client.delete(f"/api/v1/rules/scoring/{foreign_rule_id}", headers=manager_b_headers)
        assert response.status_code == 404
        assert response.json()["error_code"] == "SCORING_RULE_NOT_FOUND"


def test_list_returns_the_paginated_envelope_and_has_more_with_a_tight_limit():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        first = client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload("Regla uno"), headers=manager_headers
        )
        assert first.status_code == 201, first.text
        second = client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload("Regla dos"), headers=manager_headers
        )
        assert second.status_code == 201, second.text

        listing = client.get(
            "/api/v1/rules/scoring", params={"limit": 1}, headers=manager_headers
        )
        assert listing.status_code == 200, listing.text
        body = listing.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset", "has_more"}
        assert body["total"] == 2
        assert body["limit"] == 1
        assert body["offset"] == 0
        assert body["has_more"] is True
        assert len(body["items"]) == 1


def test_agent_role_is_forbidden_on_patch_delete_and_create():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_headers = _agent_headers(client, manager_headers)

        created = client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload(), headers=manager_headers
        )
        assert created.status_code == 201, created.text
        rule_id = created.json()["id"]

        assert client.post(
            "/api/v1/rules/scoring", json=_budget_rule_payload(), headers=agent_headers
        ).status_code == 403
        assert client.patch(
            f"/api/v1/rules/scoring/{rule_id}", json={"is_active": False}, headers=agent_headers
        ).status_code == 403
        assert client.delete(
            f"/api/v1/rules/scoring/{rule_id}", headers=agent_headers
        ).status_code == 403
