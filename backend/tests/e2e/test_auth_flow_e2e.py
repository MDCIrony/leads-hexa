import os
import uuid
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")

from fastapi.testclient import TestClient
from infrastructure.main import app


def test_full_auth_flow_bootstrap_login_and_role_enforcement():
    with TestClient(app) as client:
        # 1. Bootstrap: first agent in a fresh app instance becomes Admin, no auth needed.
        admin_email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
        bootstrap_resp = client.post(
            "/api/v1/agents",
            json={"name": "Bootstrap Admin", "email": admin_email, "team": "HQ", "password": "bootstrap-pass-123"},
        )
        assert bootstrap_resp.status_code == 201
        assert bootstrap_resp.json()["role"] == "ADMIN"

        # 2. Login with the bootstrap admin's real credentials returns a usable token.
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": admin_email, "password": "bootstrap-pass-123"},
        )
        assert login_resp.status_code == 200
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 3. Wrong password is rejected.
        bad_login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": admin_email, "password": "wrong-password"},
        )
        assert bad_login_resp.status_code == 401

        # 4. Bootstrap window is closed: creating a second agent with no token now fails.
        second_resp = client.post(
            "/api/v1/agents",
            json={"name": "Second", "email": f"second_{uuid.uuid4().hex[:6]}@test.com", "team": "Sales", "password": "x"},
        )
        assert second_resp.status_code == 401

        # 5. The admin token can create a Manager for a specific tenant.
        tenant_id = str(uuid.uuid4())
        manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
        manager_resp = client.post(
            "/api/v1/agents",
            json={
                "name": "Manager", "email": manager_email, "team": "Sales",
                "password": "manager-pass-123", "role": "MANAGER", "tenant_id": tenant_id,
            },
            headers=admin_headers,
        )
        assert manager_resp.status_code == 201
        assert manager_resp.json()["role"] == "MANAGER"

        manager_login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": manager_email, "password": "manager-pass-123"},
        )
        manager_token = manager_login_resp.json()["access_token"]
        manager_headers = {"Authorization": f"Bearer {manager_token}"}

        # 6. The Manager can create a scoring rule for their own tenant.
        own_rule_resp = client.post(
            f"/api/v1/tenants/{tenant_id}/rules/scoring",
            json={"name": "Test Rule", "field": "budget", "operator": "GREATER_THAN", "value": 1000, "score_delta": 10},
            headers=manager_headers,
        )
        assert own_rule_resp.status_code == 201

        # 7. The Manager is forbidden from creating a rule for a DIFFERENT tenant.
        other_tenant_id = str(uuid.uuid4())
        other_rule_resp = client.post(
            f"/api/v1/tenants/{other_tenant_id}/rules/scoring",
            json={"name": "Test Rule", "field": "budget", "operator": "GREATER_THAN", "value": 1000, "score_delta": 10},
            headers=manager_headers,
        )
        assert other_rule_resp.status_code == 403

        # 8. An AGENT-role token (default role) is forbidden from creating any rule.
        agent_email = f"agent_{uuid.uuid4().hex[:6]}@test.com"
        agent_resp = client.post(
            "/api/v1/agents",
            json={"name": "Plain Agent", "email": agent_email, "team": "Sales", "password": "agent-pass-123", "tenant_id": tenant_id},
            headers=admin_headers,
        )
        assert agent_resp.status_code == 201
        agent_login_resp = client.post("/api/v1/auth/login", data={"username": agent_email, "password": "agent-pass-123"})
        agent_headers = {"Authorization": f"Bearer {agent_login_resp.json()['access_token']}"}
        agent_rule_resp = client.post(
            f"/api/v1/tenants/{tenant_id}/rules/scoring",
            json={"name": "Test Rule", "field": "budget", "operator": "GREATER_THAN", "value": 1000, "score_delta": 10},
            headers=agent_headers,
        )
        assert agent_rule_resp.status_code == 403

        # 9. Deactivating the plain agent immediately revokes their existing token (re-fetch from repo, not JWT trust).
        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
        db = app.state.db
        uow = PostgresUnitOfWork(db)
        with uow:
            deactivated = uow.agents.get_by_id(uuid.UUID(agent_resp.json()["id"]))
            deactivated.is_active = False
            uow.agents.save(deactivated)
        revoked_resp = client.get(f"/api/v1/tenants/{tenant_id}/leads", headers=agent_headers)
        assert revoked_resp.status_code == 401
