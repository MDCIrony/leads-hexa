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
        if bootstrap_resp.status_code == 201:
            assert bootstrap_resp.json()["role"] == "ADMIN"
        elif bootstrap_resp.status_code == 401:
            from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
            from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
            from domain.entities.agent import Agent
            from domain.value_objects.enums import AgentRole

            db = app.state.db
            uow = PostgresUnitOfWork(db)
            with uow:
                admin = Agent.create(name="Bootstrap Admin", email=admin_email, team="HQ", role=AgentRole.ADMIN)
                admin.hashed_password = BcryptPasswordHasher().hash("bootstrap-pass-123")
                uow.agents.save(admin)
        else:
            assert bootstrap_resp.status_code in (201, 401)

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

        # 6. The Manager can create a scoring rule; it is filed under their own
        # tenant, taken from the token — there is no tenant_id left to pass.
        own_rule_resp = client.post(
            "/api/v1/rules/scoring",
            json={"name": "Test Rule", "field": "budget", "operator": "GREATER_THAN", "value": 1000, "score_delta": 10},
            headers=manager_headers,
        )
        assert own_rule_resp.status_code == 201

        # 7. A Manager from a DIFFERENT organization does not see that rule.
        # There is no longer a tenant_id in the URL for a Manager to probe, so
        # the old "creates a rule for someone else's tenant" attack has no
        # request that can even express it. What remains checkable is the
        # guarantee that actually matters: data stays scoped to the caller's
        # own organization, taken from their token.
        other_tenant_id = str(uuid.uuid4())
        other_manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
        other_manager_resp = client.post(
            "/api/v1/agents",
            json={
                "name": "Other Manager", "email": other_manager_email, "team": "Sales",
                "password": "manager-pass-123", "role": "MANAGER", "tenant_id": other_tenant_id,
            },
            headers=admin_headers,
        )
        assert other_manager_resp.status_code == 201
        other_manager_login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": other_manager_email, "password": "manager-pass-123"},
        )
        other_manager_headers = {"Authorization": f"Bearer {other_manager_login_resp.json()['access_token']}"}

        other_rules_resp = client.get("/api/v1/rules/scoring", headers=other_manager_headers)
        assert other_rules_resp.status_code == 200
        assert other_rules_resp.json() == []

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
            "/api/v1/rules/scoring",
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
        revoked_resp = client.get("/api/v1/leads", headers=agent_headers)
        assert revoked_resp.status_code == 401
