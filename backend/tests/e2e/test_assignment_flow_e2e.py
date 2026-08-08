import uuid

from fastapi.testclient import TestClient

from infrastructure.main import app


def _bootstrap_admin_headers(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/agents",
        json={
            "name": "Bootstrap Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@test.com",
            "password": "bootstrap-pass-123",
        },
    )
    assert resp.status_code == 201, resp.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": resp.json()["email"], "password": "bootstrap-pass-123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_org(client: TestClient, admin_headers: dict, name: str) -> dict:
    manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post(
        "/api/v1/tenants",
        json={
            "name": name,
            "manager": {"name": "Manager", "email": manager_email, "password": "manager-pass-123"},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": manager_email, "password": "manager-pass-123"},
    )
    assert login.status_code == 200, login.text
    return {
        "tenant_id": resp.json()["id"],
        "manager_headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


def test_assignment_flow_covers_the_phase_acceptance_criteria():
    """End-to-end walkthrough of F1's acceptance criteria: groups with
    capacity, priority-ordered score bands, an agent at capacity giving way
    to the next candidate, and strict tenant isolation between two
    organizations. The engine's other cascade — a rule with zero candidates
    ceding to the next rule — is exercised by
    tests/unit/domain/test_assignment_engine.py and again live over curl
    (see the phase report), since it needs overlapping bands that this
    scenario's literal 70-100 / 0-69 split does not have."""
    with TestClient(app) as client:
        # 1. Bootstrap: platform admin, one organization with its manager.
        admin_headers = _bootstrap_admin_headers(client)
        org = _create_org(client, admin_headers, f"Acme {uuid.uuid4().hex[:6]}")
        headers = org["manager_headers"]

        # 2. Two groups: Enterprise capped at one lead per agent, PYME uncapped.
        enterprise = client.post(
            "/api/v1/groups", json={"name": "Enterprise", "capacity_per_agent": 1}, headers=headers
        )
        assert enterprise.status_code == 201, enterprise.text
        enterprise_id = enterprise.json()["id"]

        pyme = client.post("/api/v1/groups", json={"name": "PYME"}, headers=headers)
        assert pyme.status_code == 201, pyme.text
        pyme_id = pyme.json()["id"]

        # 3. Three agents: two in Enterprise (capacity 1 each, so the second
        # high-score lead has somewhere deterministic to land once the first
        # agent is full), one in PYME.
        def _create_agent(group_id: str) -> str:
            resp = client.post(
                "/api/v1/agents",
                json={
                    "name": f"Agent {uuid.uuid4().hex[:6]}",
                    "email": f"agent_{uuid.uuid4().hex[:6]}@acme.test",
                    "group_id": group_id,
                    "password": "agent-pass-123",
                },
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            return resp.json()["id"]

        enterprise_agent_ids = {_create_agent(enterprise_id), _create_agent(enterprise_id)}
        pyme_agent_id = _create_agent(pyme_id)

        # 4. Two assignment rules: high scores to Enterprise (priority 10),
        # the rest to PYME (priority 1).
        high_rule = client.post(
            "/api/v1/rules/assignment",
            json={
                "name": "Enterprise band",
                "min_score": 70,
                "max_score": 100,
                "target_group_id": enterprise_id,
                "priority": 10,
            },
            headers=headers,
        )
        assert high_rule.status_code == 201, high_rule.text

        low_rule = client.post(
            "/api/v1/rules/assignment",
            json={
                "name": "PYME band",
                "min_score": 0,
                "max_score": 69,
                "target_group_id": pyme_id,
                "priority": 1,
            },
            headers=headers,
        )
        assert low_rule.status_code == 201, low_rule.text

        # Scoring: budget > 1000 gives +40, budget > 50000 gives another
        # +40, so a high-budget lead lands at 80 (Enterprise) and a modest
        # one at 40 (PYME) — both above the 30-point qualification floor,
        # both on a different side of the 70-point Enterprise threshold.
        for scoring_rule in (
            {"name": "Base budget", "field": "budget", "operator": "GREATER_THAN", "value": 1000, "score_delta": 40},
            {"name": "Big budget", "field": "budget", "operator": "GREATER_THAN", "value": 50000, "score_delta": 40},
        ):
            scoring_resp = client.post("/api/v1/rules/scoring", json=scoring_rule, headers=headers)
            assert scoring_resp.status_code == 201, scoring_resp.text

        def _ingest(budget: float) -> dict:
            resp = client.post(
                "/api/v1/intake/leads/ingest",
                json={
                    "first_name": "Lead",
                    "last_name": "Test",
                    "email": f"lead_{uuid.uuid4().hex[:6]}@example.com",
                    "company": "Prospect Co",
                    "budget": budget,
                    "industry": "Tech",
                },
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            return resp.json()

        # 5. A high-score lead lands on an Enterprise agent.
        first = _ingest(100000.0)
        assert first["score"] == 80
        assert first["assigned_agent_id"] in enterprise_agent_ids

        # 6. A second high-score lead finds that agent at capacity (1) and
        # falls to the other Enterprise agent — the "agent at capacity is
        # skipped, the lead goes to the next candidate" behaviour.
        second = _ingest(100000.0)
        assert second["score"] == 80
        assert second["assigned_agent_id"] in enterprise_agent_ids
        assert second["assigned_agent_id"] != first["assigned_agent_id"]

        # 7. A low-score lead (below the Enterprise band, above the
        # qualification floor) lands in PYME directly.
        third = _ingest(5000.0)
        assert third["score"] == 40
        assert third["assigned_agent_id"] == pyme_agent_id

        # 8. A second organization, with a group of the same name, must
        # never receive a lead meant for the first — and creating that
        # group must succeed in the first place, proving the uniqueness
        # constraint on group names is scoped per tenant, not global.
        other_org = _create_org(client, admin_headers, f"Other {uuid.uuid4().hex[:6]}")
        other_headers = other_org["manager_headers"]
        other_group = client.post("/api/v1/groups", json={"name": "Enterprise"}, headers=other_headers)
        assert other_group.status_code == 201, other_group.text
        other_agent = client.post(
            "/api/v1/agents",
            json={
                "name": "Other Agent",
                "email": f"other_{uuid.uuid4().hex[:6]}@other.test",
                "group_id": other_group.json()["id"],
                "password": "agent-pass-123",
            },
            headers=other_headers,
        )
        assert other_agent.status_code == 201, other_agent.text
        other_agent_id = other_agent.json()["id"]

        for result in (first, second, third):
            assert result["assigned_agent_id"] != other_agent_id

        # An AGENT is forbidden from administering groups and rules.
        plain_agent = client.post(
            "/api/v1/agents",
            json={
                "name": "Plain Agent",
                "email": f"plain_{uuid.uuid4().hex[:6]}@acme.test",
                "password": "plain-pass-123",
                "role": "AGENT",
            },
            headers=headers,
        )
        assert plain_agent.status_code == 201, plain_agent.text
        plain_login = client.post(
            "/api/v1/auth/login",
            data={"username": plain_agent.json()["email"], "password": "plain-pass-123"},
        )
        assert plain_login.status_code == 200, plain_login.text
        plain_headers = {"Authorization": f"Bearer {plain_login.json()['access_token']}"}

        assert client.post("/api/v1/groups", json={"name": "Nope"}, headers=plain_headers).status_code == 403
        assert (
            client.post("/api/v1/rules/assignment", json={"name": "Nope"}, headers=plain_headers).status_code
            == 403
        )
