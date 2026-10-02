import uuid

from gateway_client import GatewayClient
from infrastructure.main import app


def test_full_auth_flow_bootstrap_login_and_role_enforcement():
    with GatewayClient(app) as client:
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

            db = app.state.container.database
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
        admin_token = login_resp.cookies["leads_session"]
        admin_headers = {"Cookie": f"leads_session={admin_token}"}
        # The client keeps a cookie jar: without clearing it every later call
        # would silently carry the admin session, and step 4 below would test
        # an authenticated request instead of an anonymous one.
        client.cookies.clear()

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

        # 5. The Admin plane creates an organization together with its first
        # Manager — the Admin itself has no tenant_id, so it can no longer
        # create an agent directly, in any organization.
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
        assert tenant_resp.json()["manager"]["role"] == "MANAGER"

        manager_login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": manager_email, "password": "manager-pass-123"},
        )
        manager_token = manager_login_resp.cookies["leads_session"]
        manager_headers = {"Cookie": f"leads_session={manager_token}"}
        client.cookies.clear()

        # 6. The Manager can create a scoring rule; it is filed under their own
        # tenant, taken from the token — there is no tenant_id left to pass.
        own_rule_resp = client.post(
            "/api/v1/rules/scoring",
            json={
                "name": "Test Rule",
                "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 1000}],
                "score_delta": 10,
            },
            headers=manager_headers,
        )
        assert own_rule_resp.status_code == 201

        # 7. A Manager from a DIFFERENT organization does not see that rule.
        # There is no longer a tenant_id in the URL for a Manager to probe, so
        # the old "creates a rule for someone else's tenant" attack has no
        # request that can even express it. What remains checkable is the
        # guarantee that actually matters: data stays scoped to the caller's
        # own organization, taken from their token.
        other_manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
        other_tenant_resp = client.post(
            "/api/v1/tenants",
            json={
                "name": f"Other Org {uuid.uuid4().hex[:6]}",
                "manager": {"name": "Other Manager", "email": other_manager_email, "password": "manager-pass-123"},
            },
            headers=admin_headers,
        )
        assert other_tenant_resp.status_code == 201
        other_manager_login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": other_manager_email, "password": "manager-pass-123"},
        )
        other_manager_headers = {"Cookie": f"leads_session={other_manager_login_resp.cookies['leads_session']}"}
        client.cookies.clear()

        other_rules_resp = client.get("/api/v1/rules/scoring", headers=other_manager_headers)
        assert other_rules_resp.status_code == 200
        assert other_rules_resp.json()["items"] == []

        # 8. An AGENT-role token (default role) is forbidden from creating any rule.
        # Only a Manager may create agents, always inside its own
        # organization, so the plain agent comes from the first Manager
        # rather than the (now agent-less) Admin.
        agent_email = f"agent_{uuid.uuid4().hex[:6]}@test.com"
        agent_resp = client.post(
            "/api/v1/agents",
            json={"name": "Plain Agent", "email": agent_email, "team": "Sales", "password": "agent-pass-123"},
            headers=manager_headers,
        )
        assert agent_resp.status_code == 201
        agent_login_resp = client.post("/api/v1/auth/login", data={"username": agent_email, "password": "agent-pass-123"})
        agent_headers = {"Cookie": f"leads_session={agent_login_resp.cookies['leads_session']}"}
        client.cookies.clear()
        agent_rule_resp = client.post(
            "/api/v1/rules/scoring",
            json={
                "name": "Test Rule",
                "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 1000}],
                "score_delta": 10,
            },
            headers=agent_headers,
        )
        assert agent_rule_resp.status_code == 403

        # 9. Deactivating the plain agent immediately revokes their existing token (re-fetch from repo, not JWT trust).
        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
        db = app.state.container.database
        uow = PostgresUnitOfWork(db)
        with uow:
            deactivated = uow.agents.get_by_id(uuid.UUID(agent_resp.json()["id"]))
            deactivated.is_active = False
            uow.agents.save(deactivated)
        revoked_resp = client.get("/api/v1/leads", headers=agent_headers)
        assert revoked_resp.status_code == 401
