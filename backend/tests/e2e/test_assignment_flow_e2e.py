import uuid

from auth_helpers import admin_headers, agent_of, seed_org_manager
from gateway_client import GatewayClient, tenant_of

from infrastructure.main import app
from _admission_helpers import admit_lead


def _bootstrap_admin_headers(client: GatewayClient) -> dict:
    return admin_headers()


def _create_org(client: GatewayClient, admin: dict, name: str) -> dict:
    manager = seed_org_manager()
    return {"tenant_id": tenant_of(manager), "manager_headers": manager}


def test_assignment_flow_covers_the_phase_acceptance_criteria():
    """End-to-end walkthrough of F1's acceptance criteria: groups with
    capacity, priority-ordered score bands, an agent at capacity giving way
    to the next candidate, and strict tenant isolation between two
    organizations. The engine's other cascade — a rule with zero candidates
    ceding to the next rule — is exercised by
    tests/unit/domain/test_assignment_engine.py and again live over curl
    (see the phase report), since it needs overlapping bands that this
    scenario's literal 70-100 / 0-69 split does not have."""
    with GatewayClient(app) as client:
        # 1. One organization with its manager.
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
            return agent_of(headers, f"Agent {uuid.uuid4().hex[:6]}", group_id)[1]

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
            {
                "name": "Base budget",
                "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 1000}],
                "score_delta": 40,
            },
            {
                "name": "Big budget",
                "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 50000}],
                "score_delta": 40,
            },
        ):
            scoring_resp = client.post("/api/v1/rules/scoring", json=scoring_rule, headers=headers)
            assert scoring_resp.status_code == 201, scoring_resp.text

        def _admit(budget: float) -> dict:
            record = admit_lead(
                client,
                headers,
                {
                    "first_name": "Lead",
                    "last_name": "Test",
                    "email": f"lead_{uuid.uuid4().hex[:6]}@example.com",
                    "company": "Prospect Co",
                    "budget": budget,
                    "industry": "Tech",
                },
            )
            lead = client.get(f"/api/v1/leads/{record['lead_id']}", headers=headers)
            assert lead.status_code == 200, lead.text
            return lead.json()

        # 5. A high-score lead lands on an Enterprise agent.
        first = _admit(100000.0)
        assert first["score"] == 80
        assert first["assigned_agent_id"] in enterprise_agent_ids

        # 6. A second high-score lead finds that agent at capacity (1) and
        # falls to the other Enterprise agent — the "agent at capacity is
        # skipped, the lead goes to the next candidate" behaviour.
        second = _admit(100000.0)
        assert second["score"] == 80
        assert second["assigned_agent_id"] in enterprise_agent_ids
        assert second["assigned_agent_id"] != first["assigned_agent_id"]

        # 7. A low-score lead (below the Enterprise band, above the
        # qualification floor) lands in PYME directly.
        third = _admit(5000.0)
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
        _, other_agent_id = agent_of(other_headers, "Other Agent", other_group.json()["id"])

        for result in (first, second, third):
            assert result["assigned_agent_id"] != other_agent_id

        # An AGENT is forbidden from administering groups and rules.
        plain_headers, _ = agent_of(headers, "Plain Agent")

        assert client.post("/api/v1/groups", json={"name": "Nope"}, headers=plain_headers).status_code == 403
        assert (
            client.post("/api/v1/rules/assignment", json={"name": "Nope"}, headers=plain_headers).status_code
            == 403
        )


def test_assignment_rule_with_unknown_or_foreign_group_is_a_404_not_a_500():
    """target_group_id used to reach the database unchecked: an unknown id
    tripped the assignment_rules_target_group_id_fkey and surfaced as a raw
    500, and a group belonging to another tenant was silently accepted
    (foreign key happy, tenant boundary not). Both POST and PATCH must
    resolve the group scoped to the caller's own tenant."""
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        org = _create_org(client, admin_headers, f"Acme {uuid.uuid4().hex[:6]}")
        headers = org["manager_headers"]

        other_org = _create_org(client, admin_headers, f"Other {uuid.uuid4().hex[:6]}")
        other_group = client.post(
            "/api/v1/groups", json={"name": "Foreign"}, headers=other_org["manager_headers"]
        )
        assert other_group.status_code == 201, other_group.text
        foreign_group_id = other_group.json()["id"]

        unknown_group_id = str(uuid.uuid4())

        own_group = client.post("/api/v1/groups", json={"name": "Own"}, headers=headers)
        assert own_group.status_code == 201, own_group.text
        _, own_agent_id = agent_of(headers, "Own Agent", own_group.json()["id"])

        def _create_payload(target_group_id: str) -> dict:
            return {
                "name": "probe",
                "min_score": 0,
                "max_score": None,
                "target_group_id": target_group_id,
                "target_agent_ids": [],
                "agent_match_mode": "ANY",
                "strategy": "ROUND_ROBIN",
                "priority": 10,
                "conditions": [],
            }

        # Unknown group: fails the foreign key, must not leak as a 500.
        resp = client.post(
            "/api/v1/rules/assignment", json=_create_payload(unknown_group_id), headers=headers
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["error_code"] == "GROUP_NOT_FOUND"

        # Group that exists, but in another tenant: fkey is happy, tenant boundary is not.
        resp = client.post(
            "/api/v1/rules/assignment", json=_create_payload(foreign_group_id), headers=headers
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["error_code"] == "GROUP_NOT_FOUND"

        # No group at all: unaffected by the new check. Targets agents instead,
        # since a rule must point at a group or at concrete agents.
        no_group_payload = _create_payload(unknown_group_id)
        no_group_payload["target_group_id"] = None
        no_group_payload["target_agent_ids"] = [own_agent_id]
        resp = client.post("/api/v1/rules/assignment", json=no_group_payload, headers=headers)
        assert resp.status_code == 201, resp.text
        rule_id = resp.json()["id"]

        # PATCH reproduces the same check as POST.
        resp = client.patch(
            f"/api/v1/rules/assignment/{rule_id}",
            json={"target_group_id": unknown_group_id},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["error_code"] == "GROUP_NOT_FOUND"
