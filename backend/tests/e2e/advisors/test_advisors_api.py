"""GET and PATCH /api/v1/advisors over the gateway (ADR-0036, change 1)."""
import uuid

from domain.exceptions import DomainException
from infrastructure.main import app
from tests.advisors_sync import project_agents_of
from tests.e2e._intake_helpers import ingest_and_resolve
from tests.e2e.gateway_client import GatewayClient


def _login(client, email: str, password: str) -> dict:
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Cookie": f"leads_session={login.cookies['leads_session']}"}


def _admin(client) -> dict:
    email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
    created = client.post("/api/v1/agents", json={"name": "Admin", "email": email, "password": "admin-pass-123"})
    assert created.status_code == 201, created.text
    return _login(client, email, "admin-pass-123")


def _org(client, admin: dict) -> dict:
    email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    created = client.post("/api/v1/tenants", headers=admin, json={
        "name": f"Org {uuid.uuid4().hex[:6]}",
        "manager": {"name": "Manager", "email": email, "password": "manager-pass-123"},
    })
    assert created.status_code == 201, created.text
    return _login(client, email, "manager-pass-123")


def _agent(client, manager: dict, name: str) -> str:
    created = client.post("/api/v1/agents", headers=manager, json={
        "name": name, "email": f"{uuid.uuid4().hex[:8]}@test.com", "password": "agent-pass-123", "role": "AGENT",
    })
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _group(client, manager: dict) -> str:
    created = client.post("/api/v1/groups", headers=manager, json={"name": f"G {uuid.uuid4().hex[:6]}"})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _assigned_lead(client, manager: dict, agent_id: str) -> None:
    rule = client.post("/api/v1/rules/scoring", headers=manager, json={
        "name": "Tech", "conditions": [{"field": "industry", "operator": "EQUALS", "value": "tech"}],
        "score_delta": 50,
    })
    assert rule.status_code == 201, rule.text
    record = ingest_and_resolve(client, manager, {
        "first_name": "Lead", "last_name": "X", "email": f"{uuid.uuid4().hex[:6]}@x.test",
        "company": "Acme", "budget": 1000, "industry": "tech",
    })
    assigned = client.post(f"/api/v1/leads/{record['lead_id']}/assign", headers=manager,
                           json={"agent_id": agent_id})
    assert assigned.status_code == 200, assigned.text


def _items(client, manager: dict, **params) -> dict:
    listed = client.get("/api/v1/advisors", headers=manager, params=params)
    assert listed.status_code == 200, listed.text
    return {item["agent_id"]: item for item in listed.json()["items"]}


def test_the_manager_lists_advisors_with_their_group_and_active_load(test_db):
    with GatewayClient(app) as client:
        manager = _org(client, _admin(client))
        ana, bea = _agent(client, manager, "Ana"), _agent(client, manager, "Bea")
        project_agents_of(app.state.container.database)
        _assigned_lead(client, manager, ana)

        page = client.get("/api/v1/advisors", headers=manager, params={"limit": 2, "offset": 0}).json()

        assert (page["total"], page["limit"], page["offset"]) == (3, 2, 0)  # the manager is an advisor too
        assert set(page["items"][0]) == {"agent_id", "name", "group_id", "is_active", "active_load"}
        items = _items(client, manager)
        assert items[ana] == {"agent_id": ana, "name": "Ana", "group_id": None, "is_active": True,
                              "active_load": 1}
        assert items[bea]["active_load"] == 0


def test_patch_sets_the_group_and_the_list_filters_by_it(test_db):
    with GatewayClient(app) as client:
        manager = _org(client, _admin(client))
        ana, bea, group = _agent(client, manager, "Ana"), _agent(client, manager, "Bea"), _group(client, manager)
        project_agents_of(app.state.container.database)

        patched = client.patch(f"/api/v1/advisors/{ana}", headers=manager, json={"group_id": group})

        assert patched.status_code == 200, patched.text
        assert patched.json()["group_id"] == group
        assert list(_items(client, manager, group_id=group)) == [ana]
        client.patch(f"/api/v1/advisors/{bea}", headers=manager, json={"group_id": None})
        assert _items(client, manager, is_active="false") == {}
        cleared = client.patch(f"/api/v1/advisors/{ana}", headers=manager, json={"group_id": None})
        assert cleared.json()["group_id"] is None


def test_a_just_created_agent_is_hydrated_without_waiting_for_its_event(test_db):
    with GatewayClient(app) as client:
        manager = _org(client, _admin(client))
        ana, group = _agent(client, manager, "Ana"), _group(client, manager)
        assert ana not in _items(client, manager)

        patched = client.patch(f"/api/v1/advisors/{ana}", headers=manager, json={"group_id": group})

        assert patched.status_code == 200, patched.text
        assert app.state.container.advisor_directory._identity.calls == 1
        assert _items(client, manager, group_id=group)[ana]["name"] == "Ana"


def test_another_organizations_agent_or_group_is_a_404(test_db):
    with GatewayClient(app) as client:
        admin = _admin(client)
        manager_a, manager_b = _org(client, admin), _org(client, admin)
        mine, foreign_agent = _agent(client, manager_a, "Ana"), _agent(client, manager_b, "Bea")
        foreign_group = _group(client, manager_b)
        project_agents_of(app.state.container.database)

        agent = client.patch(f"/api/v1/advisors/{foreign_agent}", headers=manager_a, json={"group_id": None})
        group = client.patch(f"/api/v1/advisors/{mine}", headers=manager_a, json={"group_id": foreign_group})

        assert (agent.status_code, agent.json()["error_code"]) == (404, "AGENT_NOT_FOUND")
        assert (group.status_code, group.json()["error_code"]) == (404, "GROUP_NOT_FOUND")
        assert foreign_agent not in _items(client, manager_a)


def test_the_body_is_validated_strictly(test_db):
    with GatewayClient(app) as client:
        manager = _org(client, _admin(client))
        ana = _agent(client, manager, "Ana")

        extra = client.patch(f"/api/v1/advisors/{ana}", headers=manager, json={"group_id": None, "name": "x"})
        empty = client.patch(f"/api/v1/advisors/{ana}", headers=manager, json={})

        assert (extra.status_code, extra.json()["error_code"]) == (422, "VALIDATION_ERROR")
        assert empty.status_code == 422


def test_only_the_organization_manager_reaches_advisors(test_db):
    with GatewayClient(app) as client:
        manager = _org(client, _admin(client))
        email = f"{uuid.uuid4().hex[:8]}@test.com"
        client.post("/api/v1/agents", headers=manager, json={
            "name": "Ana", "email": email, "password": "agent-pass-123", "role": "AGENT"})

        assert client.get("/api/v1/advisors", headers=_login(client, email, "agent-pass-123")).status_code == 403


def test_identity_down_is_a_503(test_db, monkeypatch):
    with GatewayClient(app) as client:
        manager = _org(client, _admin(client))
        ana = _agent(client, manager, "Ana")

        def down(_agent_id):
            raise DomainException("identity is unavailable", error_code="SERVICE_UNAVAILABLE")

        monkeypatch.setattr(app.state.container.advisor_directory._identity, "fetch", down)
        response = client.patch(f"/api/v1/advisors/{ana}", headers=manager, json={"group_id": None})

        assert (response.status_code, response.json()["error_code"]) == (503, "SERVICE_UNAVAILABLE")
