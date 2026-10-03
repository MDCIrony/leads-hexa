import uuid

from tests.e2e.helpers.gateway_client import GatewayClient
from infrastructure.main import app

from tests.e2e.helpers.admission_helpers import admit_lead
from tests.e2e.helpers.auth_helpers import admin_headers, manager_headers, seed_agent


def _manager_auth_headers(tenant_id: str) -> dict:
    """`list_leads` scopes to the caller's own tenant, taken from the verified
    token, so listing a given tenant's leads requires a Manager of that tenant
    rather than a tenant-less Admin."""
    return manager_headers(tenant_id)


def _agent_auth_headers(tenant_id: str, group_id: str = None) -> tuple[dict, str]:
    """An AGENT of the tenant, already in the advisors projection."""
    return seed_agent(tenant_id, "Agent", group_id)


def _admin_auth_headers() -> dict:
    """The platform ADMIN, which has no tenant."""
    return admin_headers()


def _create_group(tenant_id: str) -> str:
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from domain.groups.sales_group import SalesGroup

    db = app.state.container.database
    uow = PostgresUnitOfWork(db)
    group = SalesGroup.create(tenant_id=tenant_id, name=f"Group {uuid.uuid4().hex[:6]}")
    with uow:
        uow.groups.save(group)
    return str(group.id)


def test_an_admitted_lead_is_readable_through_the_api():
    tenant_id = str(uuid.uuid4())
    payload = {
        "first_name": "Maria",
        "last_name": "Gomez",
        "email": "mgomez@techcorp.com",
        "company": "TechCorp Inc",
        "budget": 15000.0,
        "industry": "Technology",
        "custom_attributes": {"employee_count": 150},
        "phone": "+525551234567"
    }

    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        record = admit_lead(client, headers, payload)
        assert record["lead_id"]

        lead = client.get(f"/api/v1/leads/{record['lead_id']}", headers=headers)
        assert lead.status_code == 200
        data = lead.json()
        # UNASSIGNED is possible: this tenant has no assignment rule.
        assert data["status"] in ("NEW", "QUALIFIED", "DISQUALIFIED", "ASSIGNED", "UNASSIGNED")
        assert "score" in data

def test_list_leads_by_tenant_endpoint():
    tenant_id = str(uuid.uuid4())
    payload = {
        "first_name": "Laura",
        "last_name": "Gomez",
        "email": "laura@example.com",
        "company": "DesignCorp",
        "budget": 15000.0,
        "industry": "Design"
    }

    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        admit_lead(client, headers, payload)

        response = client.get("/api/v1/leads", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert data["total"] >= 1
        assert data["limit"] == 100
        assert data["offset"] == 0
        assert isinstance(data["items"], list)
        assert data["items"][0]["email"] == "laura@example.com"


def test_list_leads_pagination_has_more_flag():
    tenant_id = str(uuid.uuid4())
    base_payload = {
        "company": "DesignCorp",
        "budget": 15000.0,
        "industry": "Design",
    }

    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        for i in range(3):
            admit_lead(client, headers, {
                **base_payload,
                "first_name": f"Lead{i}",
                "last_name": "Test",
                "email": f"lead{i}@example.com",
            })

        response = client.get("/api/v1/leads?limit=2&offset=0", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["has_more"] is True

        response = client.get("/api/v1/leads?limit=2&offset=2", headers=headers)
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_more"] is False


def test_list_leads_filters_by_status_and_total_reflects_the_filter():
    # The central assertion of the filters task: total/has_more must come
    # from the filtered count, not the tenant's whole pipeline.
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        agent_headers, agent_id = _agent_auth_headers(tenant_id)

        assigned = admit_lead(client, headers, {
            "first_name": "Ana", "last_name": "Soto", "email": "ana@filters.test",
            "company": "FiltersCo", "budget": 1000.0, "industry": "Tech",
        })
        other = admit_lead(client, headers, {
            "first_name": "Bea", "last_name": "Ruiz", "email": "bea@filters.test",
            "company": "FiltersCo", "budget": 1000.0, "industry": "Tech",
        })

        assign_resp = client.post(
            f"/api/v1/leads/{assigned['lead_id']}/assign", json={"agent_id": agent_id}, headers=headers,
        )
        assert assign_resp.status_code == 200, assign_resp.text
        discard_resp = client.post(
            f"/api/v1/leads/{other['lead_id']}/discard",
            json={"reason": "No cumple criterios"},
            headers=headers,
        )
        assert discard_resp.status_code == 200, discard_resp.text

        response = client.get("/api/v1/leads?status=ASSIGNED", headers=headers)
        assert response.status_code == 200
        data = response.json()
        ids = [item["id"] for item in data["items"]]
        assert assigned["lead_id"] in ids
        assert other["lead_id"] not in ids
        assert data["total"] == len(data["items"])
        assert data["has_more"] is False


def test_list_leads_invalid_status_returns_400():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads?status=BASURA", headers=headers)
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_LEAD_STATUS"


def test_list_leads_search_finds_by_company_and_excludes_others():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        match = admit_lead(client, headers, {
            "first_name": "Carlos", "last_name": "Diaz", "email": "carlos@search.test",
            "company": "UniqueCorpXYZ", "budget": 1000.0, "industry": "Tech",
        })
        admit_lead(client, headers, {
            "first_name": "Dana", "last_name": "Vega", "email": "dana@search.test",
            "company": "SomethingElse", "budget": 1000.0, "industry": "Tech",
        })

        response = client.get("/api/v1/leads?q=UniqueCorpXYZ", headers=headers)
        assert response.status_code == 200
        data = response.json()
        ids = [item["id"] for item in data["items"]]
        assert match["lead_id"] in ids
        assert len(ids) == 1


def test_list_leads_filters_by_group_id_covers_every_agent_in_the_group():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        group_id = _create_group(tenant_id)
        _, agent_one = _agent_auth_headers(tenant_id, group_id=group_id)
        _, agent_two = _agent_auth_headers(tenant_id, group_id=group_id)

        lead_one = admit_lead(client, headers, {
            "first_name": "Eva", "last_name": "Ruiz", "email": "eva@group.test",
            "company": "GroupCo", "budget": 1000.0, "industry": "Tech",
        })
        lead_two = admit_lead(client, headers, {
            "first_name": "Fer", "last_name": "Lopez", "email": "fer@group.test",
            "company": "GroupCo", "budget": 1000.0, "industry": "Tech",
        })
        client.post(f"/api/v1/leads/{lead_one['lead_id']}/assign", json={"agent_id": agent_one}, headers=headers)
        client.post(f"/api/v1/leads/{lead_two['lead_id']}/assign", json={"agent_id": agent_two}, headers=headers)

        response = client.get(f"/api/v1/leads?group_id={group_id}", headers=headers)
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["items"]]
        assert lead_one["lead_id"] in ids
        assert lead_two["lead_id"] in ids


def test_list_leads_combines_two_filters_with_and():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        target = admit_lead(client, headers, {
            "first_name": "Gia", "last_name": "Nova", "email": "gia@combo.test",
            "company": "ComboMatchCo", "budget": 1000.0, "industry": "Tech",
        })
        client.post(
            f"/api/v1/leads/{target['lead_id']}/discard",
            json={"reason": "No cumple criterios"},
            headers=headers,
        )
        # Same company, but never discarded: matches q alone, not both filters together.
        admit_lead(client, headers, {
            "first_name": "Hugo", "last_name": "Rey", "email": "hugo@combo.test",
            "company": "ComboMatchCo", "budget": 1000.0, "industry": "Tech",
        })

        response = client.get("/api/v1/leads?status=DISCARDED&q=ComboMatchCo", headers=headers)
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["items"]]
        assert ids == [target["lead_id"]]


def test_list_my_leads_filters_by_status_and_stays_scoped_to_the_caller():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        agent_headers, agent_id = _agent_auth_headers(tenant_id)
        _, other_agent_id = _agent_auth_headers(tenant_id)

        mine = admit_lead(client, headers, {
            "first_name": "Ivan", "last_name": "Solis", "email": "ivan@mine.test",
            "company": "MineCo", "budget": 1000.0, "industry": "Tech",
        })
        colleague_lead = admit_lead(client, headers, {
            "first_name": "Jana", "last_name": "Ortiz", "email": "jana@mine.test",
            "company": "MineCo", "budget": 1000.0, "industry": "Tech",
        })
        client.post(f"/api/v1/leads/{mine['lead_id']}/assign", json={"agent_id": agent_id}, headers=headers)
        client.post(
            f"/api/v1/leads/{colleague_lead['lead_id']}/assign", json={"agent_id": other_agent_id}, headers=headers,
        )

        # assigned_agent_id is not a declared parameter here: it is silently
        # ignored rather than widening the scope to a colleague's leads.
        response = client.get(
            f"/api/v1/leads/mine?status=ASSIGNED&assigned_agent_id={other_agent_id}", headers=agent_headers,
        )
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["items"]]
        assert ids == [mine["lead_id"]]


def test_list_leads_filters_respect_tenant_isolation():
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        admit_lead(client, headers_b, {
            "first_name": "Karl", "last_name": "Beta", "email": "karl@isolation.test",
            "company": "IsolationCo", "budget": 1000.0, "industry": "Tech",
        })

        response = client.get("/api/v1/leads?q=IsolationCo", headers=headers_a)
        assert response.status_code == 200
        assert response.json()["items"] == []


def test_lead_stats_is_not_swallowed_by_the_parametric_lead_id_route():
    """Fixes the route-declaration order bug in place: with /stats declared
    after /{lead_id}, this request would 422 as an invalid UUID instead of
    reaching the stats endpoint."""
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads/stats", headers=headers)

        assert response.status_code == 200
        assert "by_status" in response.json()


def test_lead_stats_returns_its_keys_and_stays_internally_consistent():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        group_id = _create_group(tenant_id)
        agent_headers, agent_id = _agent_auth_headers(tenant_id, group_id=group_id)

        assigned = admit_lead(client, headers, {
            "first_name": "Lea", "last_name": "Funes", "email": "lea@stats.test",
            "company": "StatsCo", "budget": 1000.0, "industry": "Tech",
        })
        client.post(f"/api/v1/leads/{assigned['lead_id']}/assign", json={"agent_id": agent_id}, headers=headers)

        response = client.get("/api/v1/leads/stats", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"total", "by_status", "unassigned", "load_by_agent"}
        # by_status always carries the six LeadStatus values, zero where empty.
        assert set(body["by_status"].keys()) == {
            "NEW", "QUALIFIED", "DISQUALIFIED", "UNASSIGNED", "ASSIGNED", "DISCARDED",
        }
        # The two assertions that keep the numbers from contradicting each other.
        assert body["total"] == sum(body["by_status"].values())
        assert body["unassigned"] == body["by_status"]["UNASSIGNED"]
        assert body["by_status"]["ASSIGNED"] >= 1
        loaded = next(a for a in body["load_by_agent"] if a["agent_id"] == agent_id)
        assert loaded["name"] == "Agent"
        assert loaded["active_leads"] >= 1


def test_lead_stats_excludes_leads_from_other_organizations():
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        admit_lead(client, headers_b, {
            "first_name": "Otto", "last_name": "Vera", "email": "otto@other-org.test",
            "company": "OtherOrgCo", "budget": 1000.0, "industry": "Tech",
        })

        response = client.get("/api/v1/leads/stats", headers=headers_a)

        assert response.status_code == 200
        assert response.json()["total"] == 0


def test_lead_stats_forbidden_for_agent_and_platform_admin():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        agent_headers, _ = _agent_auth_headers(tenant_id)
        admin_headers = _admin_auth_headers()

        assert client.get("/api/v1/leads/stats", headers=agent_headers).status_code == 403
        assert client.get("/api/v1/leads/stats", headers=admin_headers).status_code == 403


def test_lead_stats_rejects_a_from_later_than_to():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        headers = _manager_auth_headers(tenant_id)

        response = client.get(
            "/api/v1/leads/stats?from=2030-01-01&to=2020-01-01", headers=headers,
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_DATE_RANGE"
