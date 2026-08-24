import os
import uuid

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from domain.value_objects.enums import AgentRole


def _get_auth_headers(client: TestClient) -> dict:
    """Return bearer headers for a real, persisted ADMIN agent.

    `get_current_agent` looks the bearer id up in the database, so a token
    minted for a made-up id always 401s once the table is genuinely empty
    between tests. With no active agents this rides the bootstrap rule
    (first unauthenticated POST becomes ADMIN); otherwise it promotes one
    of the agents already there. Either way the id is real.
    """
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    db = app.state.container.database
    uow = PostgresUnitOfWork(db)
    with uow:
        active_agents = uow.agents.list_active()
        if active_agents:
            admin_agent = active_agents[0]
            admin_agent.role = AgentRole.ADMIN
            uow.agents.save(admin_agent)
            admin_id = str(admin_agent.id)

    if not active_agents:
        bootstrap_resp = client.post(
            "/api/v1/agents",
            json={
                "name": "Bootstrap Admin",
                "email": f"bootstrap_{uuid.uuid4().hex[:6]}@test.com",
                "team": "HQ",
                "password": "bootstrap-pass-123",
            },
        )
        assert bootstrap_resp.status_code == 201
        admin_id = bootstrap_resp.json()["id"]

    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
    admin_token = token_service.issue(TokenClaims(agent_id=admin_id, role="ADMIN", tenant_id=None))
    return {"Authorization": f"Bearer {admin_token}"}


def _manager_auth_headers(client: TestClient) -> dict:
    """`list_agents` and `get_agent` are scoped to the caller's organization
    (§7.3), so exercising them now requires a real Manager created through
    the platform plane rather than the all-reaching Admin `_get_auth_headers`
    used to provide.
    """
    bootstrap_resp = client.post(
        "/api/v1/agents",
        json={
            "name": "Platform Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@test.com",
            "team": "HQ",
            "password": "admin-pass-123",
        },
    )
    assert bootstrap_resp.status_code == 201
    admin_login = client.post(
        "/api/v1/auth/login",
        data={"username": bootstrap_resp.json()["email"], "password": "admin-pass-123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    tenant_resp = client.post(
        "/api/v1/tenants",
        json={
            "name": f"Org {uuid.uuid4().hex[:6]}",
            "manager": {"name": "Manager", "email": manager_email, "password": "manager-pass-123"},
        },
        headers=admin_headers,
    )
    assert tenant_resp.status_code == 201

    manager_login = client.post(
        "/api/v1/auth/login",
        data={"username": manager_email, "password": "manager-pass-123"},
    )
    assert manager_login.status_code == 200
    return {"Authorization": f"Bearer {manager_login.json()['access_token']}"}


def test_get_agent_not_found_returns_domain_error_shape():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        response = client.get(f"/api/v1/agents/{uuid.uuid4()}", headers=headers)
        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert data["error_code"] == "AGENT_NOT_FOUND"
        assert "message" in data


def test_create_agent_rejects_malformed_email():
    with TestClient(app) as client:
        headers = _get_auth_headers(client)
        response = client.post(
            "/api/v1/agents",
            json={"name": "Bad Agent", "email": "not-an-email", "team": "Sales", "password": "pass"},
            headers=headers,
        )
        assert response.status_code == 422


def test_list_agents_returns_pagination_metadata():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        group_resp = client.post(
            "/api/v1/groups",
            json={"name": f"Group {uuid.uuid4().hex[:6]}"},
            headers=headers,
        )
        assert group_resp.status_code == 201
        group_id = group_resp.json()["id"]
        for i in range(3):
            client.post(
                "/api/v1/agents",
                json={
                    "name": f"Agent {i}",
                    "email": f"agent{i}_{uuid.uuid4().hex[:6]}@example.com",
                    "group_id": group_id,
                    "password": "password123",
                },
                headers=headers,
            )

        response = client.get(f"/api/v1/agents?group_id={group_id}&limit=2&offset=0", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["has_more"] is True

        response = client.get(f"/api/v1/agents?group_id={group_id}&limit=2&offset=2", headers=headers)
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_more"] is False


def test_create_agent_rejects_duplicate_email_in_same_tenant():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        first = client.post(
            "/api/v1/agents",
            json={"name": "Agent A", "email": email, "password": "password123"},
            headers=headers,
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/agents",
            json={"name": "Agent B", "email": email, "password": "password123"},
            headers=headers,
        )
        assert second.status_code == 400
        data = second.json()
        assert data["error_code"] == "EMAIL_ALREADY_EXISTS"


def _create_org_manager_headers(client: TestClient, admin_headers: dict) -> dict:
    """Creates a second organization under an already-bootstrapped Admin.

    `_manager_auth_headers` bootstraps its own Admin, which only works once
    the agents table is empty — calling it twice in one test fails the
    second time with a real Manager `401`, not the scenario under test.
    """
    manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    tenant_resp = client.post(
        "/api/v1/tenants",
        json={
            "name": f"Org {uuid.uuid4().hex[:6]}",
            "manager": {"name": "Manager", "email": manager_email, "password": "manager-pass-123"},
        },
        headers=admin_headers,
    )
    assert tenant_resp.status_code == 201

    manager_login = client.post(
        "/api/v1/auth/login",
        data={"username": manager_email, "password": "manager-pass-123"},
    )
    assert manager_login.status_code == 200
    return {"Authorization": f"Bearer {manager_login.json()['access_token']}"}


def test_reactivating_an_agent_restores_login_and_default_listing():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        email = f"reactivate_{uuid.uuid4().hex[:6]}@example.com"
        password = "password123"
        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "Ana Reactivable", "email": email, "password": password},
            headers=headers,
        )
        assert create_resp.status_code == 201
        agent_id = create_resp.json()["id"]

        deactivate_resp = client.delete(f"/api/v1/agents/{agent_id}", headers=headers)
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["is_active"] is False

        # Deactivated: gone from the default listing, present under the
        # explicit is_active=false view, and total matches both.
        default_list = client.get("/api/v1/agents", headers=headers)
        assert agent_id not in [a["id"] for a in default_list.json()["items"]]
        inactive_list = client.get("/api/v1/agents?is_active=false", headers=headers)
        inactive_ids = [a["id"] for a in inactive_list.json()["items"]]
        assert agent_id in inactive_ids
        assert inactive_list.json()["total"] == len(inactive_ids)
        assert default_list.json()["total"] == len(default_list.json()["items"])

        reactivate_resp = client.patch(
            f"/api/v1/agents/{agent_id}", json={"is_active": True}, headers=headers
        )
        assert reactivate_resp.status_code == 200
        assert reactivate_resp.json()["is_active"] is True

        # The assertion that gives the task its point: reactivating restores
        # real login access, not just the database flag.
        login_resp = client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}
        )
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()

        # Reactivated: back in the default listing.
        default_list_after = client.get("/api/v1/agents", headers=headers)
        assert agent_id in [a["id"] for a in default_list_after.json()["items"]]


def test_patch_without_is_active_leaves_activation_state_untouched():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "Bruno", "email": f"bruno_{uuid.uuid4().hex[:6]}@example.com", "password": "password123"},
            headers=headers,
        )
        agent_id = create_resp.json()["id"]

        response = client.patch(f"/api/v1/agents/{agent_id}", json={"name": "Bruno R."}, headers=headers)
        assert response.status_code == 200
        assert response.json()["is_active"] is True


def test_reactivate_agent_of_another_organization_returns_not_found():
    with TestClient(app) as client:
        admin_headers = _get_auth_headers(client)
        first_org_headers = _create_org_manager_headers(client, admin_headers)
        second_org_headers = _create_org_manager_headers(client, admin_headers)

        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "Ajena", "email": f"ajena_{uuid.uuid4().hex[:6]}@example.com", "password": "password123"},
            headers=first_org_headers,
        )
        agent_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/agents/{agent_id}", json={"is_active": True}, headers=second_org_headers
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "AGENT_NOT_FOUND"


def test_agent_role_cannot_patch_another_agent():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "Sub", "email": f"sub_{uuid.uuid4().hex[:6]}@example.com", "password": "password123"},
            headers=headers,
        )
        agent_id = create_resp.json()["id"]
        agent_login = client.post(
            "/api/v1/auth/login",
            data={"username": create_resp.json()["email"], "password": "password123"},
        )
        agent_headers = {"Authorization": f"Bearer {agent_login.json()['access_token']}"}

        response = client.patch(
            f"/api/v1/agents/{agent_id}", json={"is_active": True}, headers=agent_headers
        )
        assert response.status_code == 403


def test_issuing_an_integration_credential_without_kafka_fails_atomically():
    """backend-test has no reachable Kafka (no KAFKA_BOOTSTRAP_SERVERS in its
    compose environment, same hermetic reasoning as RabbitMQ in ADR-0027):
    this is exactly the case the suite can exercise without a real broker —
    that a failed provisioning never leaves an orphaned agent row behind."""
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)

        response = client.post("/api/v1/agents/integration-credential", headers=headers)
        assert response.status_code == 503
        assert response.json()["error_code"] == "MESSAGING_UNAVAILABLE"

        agents = client.get("/api/v1/agents?is_active=true", headers=headers)
        assert all(a["role"] != "INTEGRATION" for a in agents.json()["items"])


def test_create_agent_rejects_duplicate_email_across_tenants():
    with TestClient(app) as client:
        admin_headers = _get_auth_headers(client)
        first_org_headers = _create_org_manager_headers(client, admin_headers)
        second_org_headers = _create_org_manager_headers(client, admin_headers)
        email = f"cross_{uuid.uuid4().hex[:6]}@example.com"

        first = client.post(
            "/api/v1/agents",
            json={"name": "Agent A", "email": email, "password": "password123"},
            headers=first_org_headers,
        )
        assert first.status_code == 201

        # Same email, different organization: still rejected, because login
        # resolves accounts by email alone (auth_use_cases.py:20-21).
        second = client.post(
            "/api/v1/agents",
            json={"name": "Agent B", "email": email, "password": "password123"},
            headers=second_org_headers,
        )
        assert second.status_code == 400
        data = second.json()
        assert data["error_code"] == "EMAIL_ALREADY_EXISTS"

