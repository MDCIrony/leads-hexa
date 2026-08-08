import uuid

from fastapi.testclient import TestClient

from infrastructure.main import app


def _bootstrap_admin(client: TestClient) -> str:
    response = client.post(
        "/api/v1/agents",
        json={
            "name": "Platform Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@platform.test",
            "team": "HQ",
            "password": "admin-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "ADMIN"
    login = client.post(
        "/api/v1/auth/login",
        data={"username": response.json()["email"], "password": "admin-pass-123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _create_org(client: TestClient, admin_token: str) -> tuple[str, str]:
    """Tenant, manager login, and a baseline scoring rule so a lead ingested
    with industry="tech" always reaches an assignable status (QUALIFIED, then
    UNASSIGNED once the engine finds no routing rule) instead of NEW."""
    email = f"manager_{uuid.uuid4().hex[:6]}@acme.test"
    created = client.post(
        "/api/v1/tenants",
        json={
            "name": f"Acme {uuid.uuid4().hex[:6]}",
            "manager": {"name": "Manager", "email": email, "password": "manager-pass-123"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert created.status_code == 201, created.text
    tenant_id = created.json()["id"]

    login = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "manager-pass-123"}
    )
    assert login.status_code == 200, login.text
    manager_token = login.json()["access_token"]

    rule = client.post(
        "/api/v1/rules/scoring",
        json={
            "name": "Tech leads",
            "field": "industry",
            "operator": "EQUALS",
            "value": "tech",
            "score_delta": 50,
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert rule.status_code == 201, rule.text

    return manager_token, tenant_id


def _create_agent(client: TestClient, manager_token: str) -> tuple[str, str]:
    email = f"agent_{uuid.uuid4().hex[:6]}@acme.test"
    created = client.post(
        "/api/v1/agents",
        json={"name": "Sales Agent", "email": email, "password": "agent-pass-123", "role": "AGENT"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert created.status_code == 201, created.text
    login = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "agent-pass-123"}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], created.json()["id"]


def _ingest_qualified_lead(client: TestClient, manager_token: str, tenant_id: str) -> str:
    ingested = client.post(
        "/api/v1/intake/leads/ingest",
        json={
            "first_name": "Lead",
            "last_name": uuid.uuid4().hex[:6],
            "email": f"lead_{uuid.uuid4().hex[:6]}@x.test",
            "company": "Acme",
            "budget": 1000,
            "industry": "tech",
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert ingested.status_code == 201, ingested.text
    assert ingested.json()["status"] == "UNASSIGNED", ingested.text
    return ingested.json()["lead_id"]


def _ingest_and_assign(client: TestClient, manager_token: str, tenant_id: str, agent_id: str) -> str:
    lead_id = _ingest_qualified_lead(client, manager_token, tenant_id)
    assigned = client.post(
        f"/api/v1/leads/{lead_id}/assign",
        json={"agent_id": agent_id},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert assigned.status_code == 200, assigned.text
    return lead_id


def test_an_agent_sees_only_their_own_leads_on_mine(test_db):
    """The agent's only door to their leads: GET /leads is manager-only."""
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        agent_token, agent_id = _create_agent(client, manager_token)
        mine_id = _ingest_and_assign(client, manager_token, tenant_id, agent_id)
        _ingest_and_assign(client, manager_token, tenant_id, _create_agent(client, manager_token)[1])

        mine = client.get("/api/v1/leads/mine", headers={"Authorization": f"Bearer {agent_token}"})

        assert mine.status_code == 200, mine.text
        assert [item["id"] for item in mine.json()["items"]] == [mine_id]


def test_the_platform_admin_is_refused_on_mine(test_db):
    """The admin has no tenant, so it must reach no operational data."""
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)

        refused = client.get(
            "/api/v1/leads/mine", headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert refused.status_code == 403, refused.text


def test_a_manager_can_also_call_mine_and_gets_their_own(test_db):
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        manager_id = client.get("/api/v1/auth/me", headers=manager_headers).json()["id"]
        mine_id = _ingest_and_assign(client, manager_token, tenant_id, manager_id)

        mine = client.get("/api/v1/leads/mine", headers=manager_headers)

        assert mine.status_code == 200, mine.text
        assert [item["id"] for item in mine.json()["items"]] == [mine_id]


def test_an_agent_cannot_read_a_colleagues_lead_detail(test_db):
    """404, not 403: a refusal would confirm the lead exists in the org."""
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        agent_a_token, _ = _create_agent(client, manager_token)
        _, agent_b_id = _create_agent(client, manager_token)
        colleagues_lead_id = _ingest_and_assign(client, manager_token, tenant_id, agent_b_id)

        response = client.get(
            f"/api/v1/leads/{colleagues_lead_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )

        assert response.status_code == 404, response.text


def test_a_manager_assigns_a_lead_by_hand(test_db):
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        _, agent_id = _create_agent(client, manager_token)
        lead_id = _ingest_qualified_lead(client, manager_token, tenant_id)

        response = client.post(
            f"/api/v1/leads/{lead_id}/assign",
            json={"agent_id": agent_id},
            headers={"Authorization": f"Bearer {manager_token}"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ASSIGNED"
        assert response.json()["assigned_at"] is not None


def test_assigning_an_agent_of_another_organization_fails(test_db):
    """The agent is resolved scoped to the caller's own organization
    (get_by_id_and_tenant), so one from another tenant reads back as missing
    (404 AGENT_NOT_FOUND) before the domain's own cross-tenant guard runs."""
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_a, tenant_a = _create_org(client, admin_token)
        manager_b, _ = _create_org(client, admin_token)
        _, foreign_agent_id = _create_agent(client, manager_b)
        lead_id = _ingest_qualified_lead(client, manager_a, tenant_a)

        response = client.post(
            f"/api/v1/leads/{lead_id}/assign",
            json={"agent_id": foreign_agent_id},
            headers={"Authorization": f"Bearer {manager_a}"},
        )

        assert response.status_code == 404, response.text
        assert response.json()["error_code"] == "AGENT_NOT_FOUND"


def test_an_agent_cannot_assign(test_db):
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        agent_token, agent_id = _create_agent(client, manager_token)
        lead_id = _ingest_qualified_lead(client, manager_token, tenant_id)

        response = client.post(
            f"/api/v1/leads/{lead_id}/assign",
            json={"agent_id": agent_id},
            headers={"Authorization": f"Bearer {agent_token}"},
        )

        assert response.status_code == 403, response.text


def test_a_manager_discards_with_a_reason(test_db):
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        lead_id = _ingest_qualified_lead(client, manager_token, tenant_id)

        response = client.post(
            f"/api/v1/leads/{lead_id}/discard",
            json={"reason": "Presupuesto insuficiente"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "DISCARDED"
        assert response.json()["discard_reason"] == "Presupuesto insuficiente"


def test_discarding_without_a_reason_is_refused(test_db):
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        lead_id = _ingest_qualified_lead(client, manager_token, tenant_id)

        response = client.post(
            f"/api/v1/leads/{lead_id}/discard",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {manager_token}"},
        )

        assert response.status_code == 400, response.text
        assert response.json()["error_code"] == "DISCARD_WITHOUT_REASON"


def test_the_lead_detail_carries_the_applied_rule_breakdown(test_db):
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        manager_token, tenant_id = _create_org(client, admin_token)
        lead_id = _ingest_qualified_lead(client, manager_token, tenant_id)

        detail = client.get(
            f"/api/v1/leads/{lead_id}", headers={"Authorization": f"Bearer {manager_token}"}
        )

        assert detail.status_code == 200, detail.text
        breakdown = detail.json()["score_breakdown"]
        assert len(breakdown) == 1
        assert set(breakdown[0].keys()) == {"rule_id", "name", "score_delta"}
        assert breakdown[0]["score_delta"] == 50
