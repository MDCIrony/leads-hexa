from auth_helpers import admin_headers, agent_of, seed_org_manager
from gateway_client import GatewayClient

from infrastructure.main import app
from _admission_helpers import admit_lead


def _bootstrap_admin_headers(client: GatewayClient) -> dict:
    """The platform ADMIN; organizations are identity's, so it only names the caller now."""
    return admin_headers()


def _create_org_manager_headers(client: GatewayClient, admin_headers: dict) -> dict:
    """The manager of a fresh organization."""
    return seed_org_manager()


def _agent_headers(client: GatewayClient, manager_headers: dict) -> dict:
    """A plain AGENT inside the manager's organization."""
    return agent_of(manager_headers)[0]


def _no_contact_payload(name: str = "Sin forma de contactar") -> dict:
    """Two conditions ANDed on one rule: the shape the phase exists for."""
    return {
        "name": name,
        "conditions": [
            {"field": "phone", "operator": "IS_EMPTY"},
            {"field": "email", "operator": "IS_EMPTY"},
        ],
    }


def test_create_list_update_and_delete_cycle():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/rules/disqualification", json=_no_contact_payload(), headers=manager_headers
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["name"] == "Sin forma de contactar"
        assert body["is_active"] is True
        rule_id = body["id"]

        listing = client.get("/api/v1/rules/disqualification", headers=manager_headers)
        assert listing.status_code == 200, listing.text
        assert rule_id in {item["id"] for item in listing.json()["items"]}

        updated = client.patch(
            f"/api/v1/rules/disqualification/{rule_id}",
            json={"is_active": False, "priority": 5},
            headers=manager_headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["is_active"] is False
        assert updated.json()["priority"] == 5

        deleted = client.delete(f"/api/v1/rules/disqualification/{rule_id}", headers=manager_headers)
        assert deleted.status_code == 204, deleted.text

        after = client.get("/api/v1/rules/disqualification", headers=manager_headers)
        assert rule_id not in {item["id"] for item in after.json()["items"]}


def test_create_with_no_conditions_is_rejected():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        response = client.post(
            "/api/v1/rules/disqualification",
            json={"name": "Vacía", "conditions": []},
            headers=manager_headers,
        )

        assert response.status_code == 400, response.text
        assert response.json()["error_code"] == "INVALID_RULE_CONDITIONS"


def test_patch_and_delete_of_another_organizations_rule_return_404():
    # No single-rule GET exists (list is the only read), so only PATCH and
    # DELETE — the two endpoints that take a rule_id — can 404 on it.
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_a_headers = _create_org_manager_headers(client, admin_headers)
        manager_b_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/rules/disqualification", json=_no_contact_payload(), headers=manager_a_headers
        )
        assert created.status_code == 201, created.text
        foreign_rule_id = created.json()["id"]

        patch_resp = client.patch(
            f"/api/v1/rules/disqualification/{foreign_rule_id}",
            json={"is_active": False},
            headers=manager_b_headers,
        )
        assert patch_resp.status_code == 404
        assert patch_resp.json()["error_code"] == "DISQUALIFICATION_RULE_NOT_FOUND"

        delete_resp = client.delete(
            f"/api/v1/rules/disqualification/{foreign_rule_id}", headers=manager_b_headers
        )
        assert delete_resp.status_code == 404
        assert delete_resp.json()["error_code"] == "DISQUALIFICATION_RULE_NOT_FOUND"


def test_agent_role_is_forbidden_from_all_four_endpoints():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_headers = _agent_headers(client, manager_headers)

        created = client.post(
            "/api/v1/rules/disqualification", json=_no_contact_payload(), headers=manager_headers
        )
        assert created.status_code == 201, created.text
        rule_id = created.json()["id"]

        assert client.get("/api/v1/rules/disqualification", headers=agent_headers).status_code == 403
        assert client.post(
            "/api/v1/rules/disqualification", json=_no_contact_payload(), headers=agent_headers
        ).status_code == 403
        assert client.patch(
            f"/api/v1/rules/disqualification/{rule_id}", json={"is_active": False}, headers=agent_headers
        ).status_code == 403
        assert client.delete(
            f"/api/v1/rules/disqualification/{rule_id}", headers=agent_headers
        ).status_code == 403


def test_a_lead_with_neither_phone_nor_email_is_disqualified_by_name_with_no_score():
    """Acceptance criteria 1 and 2 of the phase, end to end over HTTP."""
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        rule_name = "Sin forma de contactar"
        created = client.post(
            "/api/v1/rules/disqualification",
            json=_no_contact_payload(rule_name),
            headers=manager_headers,
        )
        assert created.status_code == 201, created.text

        record = admit_lead(
            client,
            manager_headers,
            {
                "first_name": "Carla",
                "last_name": "Sin Contacto",
                "company": "Acme",
                "budget": 1000,
                "industry": "tech",
            },
        )
        lead_id = record.get("lead_id")
        assert lead_id, record

        lead = client.get(f"/api/v1/leads/{lead_id}", headers=manager_headers)
        assert lead.status_code == 200, lead.text
        body = lead.json()

        # Criterion 2: the reason shown is the rule's name, not a score.
        assert body["status"] == "DISQUALIFIED"
        assert body["disqualification_reason"] == rule_name
        # Cut before scoring ran: no points, no breakdown to explain them.
        assert body["score"] == 0
        assert body["score_breakdown"] == []
