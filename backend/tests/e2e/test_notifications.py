import uuid
from typing import Optional

from fastapi.testclient import TestClient

from infrastructure.main import app
from _intake_helpers import ingest_and_resolve


def _bootstrap_admin_headers(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/agents",
        json={
            "name": "Platform Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@test.com",
            "password": "admin-pass-123",
        },
    )
    assert resp.status_code == 201, resp.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": resp.json()["email"], "password": "admin-pass-123"},
    )
    assert login.status_code == 200, login.text
    return {"Cookie": f"leads_session={login.cookies['leads_session']}"}


def _create_org_manager_headers(client: TestClient, admin_headers: dict) -> dict:
    manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    tenant_resp = client.post(
        "/api/v1/tenants",
        json={
            "name": f"Org {uuid.uuid4().hex[:6]}",
            "manager": {"name": "Manager", "email": manager_email, "password": "manager-pass-123"},
        },
        headers=admin_headers,
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": manager_email, "password": "manager-pass-123"},
    )
    assert login.status_code == 200, login.text
    return {"Cookie": f"leads_session={login.cookies['leads_session']}"}


def _create_agent(client: TestClient, manager_headers: dict, group_id: Optional[str] = None) -> tuple[str, dict]:
    email = f"agent_{uuid.uuid4().hex[:6]}@test.com"
    payload = {"name": "Agent", "email": email, "password": "agent-pass-123"}
    if group_id:
        payload["group_id"] = group_id
    resp = client.post("/api/v1/agents", json=payload, headers=manager_headers)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()["id"]
    login = client.post("/api/v1/auth/login", data={"username": email, "password": "agent-pass-123"})
    assert login.status_code == 200, login.text
    return agent_id, {"Cookie": f"leads_session={login.cookies['leads_session']}"}


def _route_everything_to(client: TestClient, manager_headers: dict, agent_id: str) -> None:
    """A single catch-all assignment rule: every qualified lead in this
    organization lands on this agent instead of staying UNASSIGNED."""
    resp = client.post(
        "/api/v1/rules/assignment",
        json={"name": "Catch-all", "target_agent_ids": [agent_id]},
        headers=manager_headers,
    )
    assert resp.status_code == 201, resp.text


def _lead_payload(**overrides) -> dict:
    payload = {
        "first_name": "Lead",
        "last_name": uuid.uuid4().hex[:6],
        "email": f"lead_{uuid.uuid4().hex[:6]}@test.com",
        "company": "Acme",
        "budget": 1000,
        "industry": "tech",
    }
    payload.update(overrides)
    return payload


def test_agent_with_assigned_lead_sees_one_unread_notification_with_lead_id():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_id, agent_headers = _create_agent(client, manager_headers)
        _route_everything_to(client, manager_headers, agent_id)

        record = ingest_and_resolve(client, manager_headers, _lead_payload())

        response = client.get("/api/v1/notifications", headers=agent_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 1
        assert data["unread_count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["is_read"] is False
        assert data["items"][0]["kind"] == "LEAD_ASSIGNED"
        assert data["items"][0]["lead_id"] == record["lead_id"]


def test_unread_count_reflects_reads_and_the_page_filter():
    """Four notices, one marked read: unread_count must drop by one, stay the
    recipient's total (not the page's) with no filter, and unread_only=true
    must return only the three still-unread ones."""
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_id, agent_headers = _create_agent(client, manager_headers)
        _route_everything_to(client, manager_headers, agent_id)

        for _ in range(4):
            ingest_and_resolve(client, manager_headers, _lead_payload())

        baseline = client.get("/api/v1/notifications", headers=agent_headers).json()
        assert baseline["total"] == 4
        assert baseline["unread_count"] == 4

        first_id = baseline["items"][0]["id"]
        mark_read = client.post(f"/api/v1/notifications/{first_id}/read", headers=agent_headers)
        assert mark_read.status_code == 204, mark_read.text

        after = client.get("/api/v1/notifications", headers=agent_headers).json()
        assert after["total"] == 4
        assert after["unread_count"] == 3

        unread_only = client.get("/api/v1/notifications?unread_only=true", headers=agent_headers).json()
        assert unread_only["total"] == 3
        assert unread_only["unread_count"] == 3
        assert len(unread_only["items"]) == 3
        assert all(not item["is_read"] for item in unread_only["items"])


def test_mark_all_notifications_read_zeroes_the_counter_and_is_idempotent():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_id, agent_headers = _create_agent(client, manager_headers)
        _route_everything_to(client, manager_headers, agent_id)

        for _ in range(2):
            ingest_and_resolve(client, manager_headers, _lead_payload())

        first = client.post("/api/v1/notifications/read-all", headers=agent_headers)
        assert first.status_code == 204, first.text
        assert client.get("/api/v1/notifications", headers=agent_headers).json()["unread_count"] == 0

        second = client.post("/api/v1/notifications/read-all", headers=agent_headers)
        assert second.status_code == 204, second.text
        assert client.get("/api/v1/notifications", headers=agent_headers).json()["unread_count"] == 0


def test_agent_only_sees_their_own_notifications():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        group = client.post(
            "/api/v1/groups", json={"name": "Team", "capacity_per_agent": 1}, headers=manager_headers
        )
        assert group.status_code == 201, group.text
        group_id = group.json()["id"]

        _, headers_x = _create_agent(client, manager_headers, group_id)
        _, headers_y = _create_agent(client, manager_headers, group_id)

        rule = client.post(
            "/api/v1/rules/assignment",
            json={"name": "Team rule", "target_group_id": group_id},
            headers=manager_headers,
        )
        assert rule.status_code == 201, rule.text

        # Capacity 1 per agent forces the second lead to the other agent, so
        # each of the two ends up with exactly one notice of its own.
        ingest_and_resolve(client, manager_headers, _lead_payload())
        ingest_and_resolve(client, manager_headers, _lead_payload())

        items_x = client.get("/api/v1/notifications", headers=headers_x).json()["items"]
        items_y = client.get("/api/v1/notifications", headers=headers_y).json()["items"]
        assert len(items_x) == 1
        assert len(items_y) == 1
        assert items_x[0]["lead_id"] != items_y[0]["lead_id"]


def test_marking_another_agents_notification_returns_404_not_403():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_id, headers_owner = _create_agent(client, manager_headers)
        _, headers_other = _create_agent(client, manager_headers)
        _route_everything_to(client, manager_headers, agent_id)

        ingest_and_resolve(client, manager_headers, _lead_payload())
        notification_id = client.get("/api/v1/notifications", headers=headers_owner).json()["items"][0]["id"]

        response = client.post(f"/api/v1/notifications/{notification_id}/read", headers=headers_other)
        assert response.status_code == 404, response.text
        assert response.json()["error_code"] == "NOTIFICATION_NOT_FOUND"


def test_manager_is_notified_of_unassigned_lead_and_rejected_intake():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        # No assignment rule in this organization: the qualified lead finds
        # no candidate and stays UNASSIGNED.
        unassigned = ingest_and_resolve(client, manager_headers, _lead_payload())
        assert unassigned["lead_id"], unassigned

        # No format validator on the intake schema lets a malformed email
        # reach the domain, which rejects it (INVALID_EMAIL).
        rejected = ingest_and_resolve(client, manager_headers, _lead_payload(email="not-an-email"))
        assert rejected["status"] == "REJECTED", rejected

        response = client.get("/api/v1/notifications", headers=manager_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 2
        kinds = {item["kind"] for item in data["items"]}
        assert kinds == {"LEAD_LEFT_UNASSIGNED", "INTAKE_REJECTED"}

        left_unassigned = next(item for item in data["items"] if item["kind"] == "LEAD_LEFT_UNASSIGNED")
        assert left_unassigned["lead_id"] == unassigned["lead_id"]

        intake_rejected = next(item for item in data["items"] if item["kind"] == "INTAKE_REJECTED")
        assert intake_rejected["intake_record_id"] == rejected["id"]


def test_platform_admin_cannot_call_get_notifications():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        response = client.get("/api/v1/notifications", headers=admin_headers)
        assert response.status_code == 403, response.text


def test_pagination_has_more_flag_and_unread_count_ignores_the_page():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_id, agent_headers = _create_agent(client, manager_headers)
        _route_everything_to(client, manager_headers, agent_id)

        for _ in range(3):
            ingest_and_resolve(client, manager_headers, _lead_payload())

        response = client.get("/api/v1/notifications?limit=1", headers=agent_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 3
        assert data["has_more"] is True
        assert data["unread_count"] == 3
