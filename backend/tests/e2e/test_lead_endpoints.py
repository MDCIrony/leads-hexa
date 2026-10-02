import uuid

from gateway_client import GatewayClient
from infrastructure.main import app

from _intake_helpers import ingest_and_resolve
from auth_helpers import admin_headers, manager_headers, seed_agent, seed_organization


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
    from domain.entities.sales_group import SalesGroup

    db = app.state.container.database
    uow = PostgresUnitOfWork(db)
    group = SalesGroup.create(tenant_id=tenant_id, name=f"Group {uuid.uuid4().hex[:6]}")
    with uow:
        uow.groups.save(group)
    return str(group.id)


def _seed_tenant_with_sources(tenant_id: str) -> None:
    """The intake router resolves the source itself (migration 005), so every
    ingest test needs the tenant's two default sources."""
    seed_organization(tenant_id)


def test_ingest_lead_endpoint_success():
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
        # The connection pool only exists inside the TestClient lifespan
        # (opened on FastAPI startup, closed on shutdown), so seeding must
        # happen after entering this block, not before it.
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        record = ingest_and_resolve(client, headers, payload)
        assert record["lead_id"]

        lead = client.get(f"/api/v1/leads/{record['lead_id']}", headers=headers)
        assert lead.status_code == 200
        data = lead.json()
        # UNASSIGNED joined the set in F2c: this tenant has no assignment
        # rule, and qualify() no longer has a threshold that could leave an
        # ingested lead stuck at NEW (acceptance criterion 5).
        assert data["status"] in ("NEW", "QUALIFIED", "DISQUALIFIED", "ASSIGNED", "UNASSIGNED")
        assert "score" in data

def test_ingest_lead_endpoint_invalid_email_is_accepted_and_rejected_in_the_tray():
    # V1: the schema's loose email format check is gone, so this reaches the
    # domain instead of bouncing as a 422 that would have discarded it.
    tenant_id = str(uuid.uuid4())
    payload = {
        "first_name": "Maria",
        "last_name": "Gomez",
        "email": "email-sin-arroba",
        "company": "TechCorp Inc",
        "budget": 15000.0,
        "industry": "Technology"
    }

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        record = ingest_and_resolve(client, headers, payload)
        assert record["status"] == "REJECTED"
        assert record["errors"][0]["field"] == "email"

def test_batch_upload_endpoint():
    tenant_id = str(uuid.uuid4())
    csv_content = (
        "first_name,last_name,email,company,budget,industry\n"
        "Ana,Silva,ana@company.com,CompanyA,20000,Finance\n"
        "Luis,Perez,luis@company.com,CompanyB,10000,Retail\n"
    ).encode("utf-8")

    files = {"file": ("leads.csv", csv_content, "text/csv")}

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/batch-upload", files=files, headers=headers)
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data

        records = client.get(f"/api/v1/intake/records?job_id={data['job_id']}", headers=headers)
        assert records.status_code == 200
        items = records.json()["items"]
        assert len(items) == 2
        assert all(item["status"] == "PROMOTED" for item in items)

def test_batch_upload_reports_failed_rows_without_losing_the_valid_ones():
    tenant_id = str(uuid.uuid4())
    csv_content = (
        "first_name,last_name,email,company,budget,industry\n"
        "Ana,Silva,ana@company.com,CompanyA,20000,Finance\n"
        "Mal,Formado,email-sin-arroba,CompanyB,10000,Retail\n"
        "Luis,Perez,luis@company.com,CompanyC,10000,Retail\n"
    ).encode("utf-8")

    files = {"file": ("leads.csv", csv_content, "text/csv")}

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/batch-upload", files=files, headers=headers)
        assert response.status_code == 202
        data = response.json()

        records = client.get(f"/api/v1/intake/records?job_id={data['job_id']}", headers=headers).json()
        items = records["items"]
        assert len(items) == 3

        promoted = [item for item in items if item["status"] == "PROMOTED"]
        rejected = [item for item in items if item["status"] == "REJECTED"]
        assert len(promoted) == 2
        assert len(rejected) == 1

        # The row must say WHERE it was kept, not just that it failed. Without
        # this the manager has to pair the response against the inbox by
        # matching contents, which is ambiguous as soon as two rows look alike.
        failed = rejected[0]
        assert failed["payload"]["email"] == "email-sin-arroba"
        assert failed["errors"][0]["error_code"] == "INVALID_EMAIL"
        assert failed["id"]

        # A bad row must not drag the good ones down with it: only the 2
        # valid rows are actually persisted for this tenant.
        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
        uow = PostgresUnitOfWork(app.state.container.database)
        with uow:
            persisted_count = uow.leads.count_by_tenant(uuid.UUID(tenant_id))
        assert persisted_count == 2

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
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)

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
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        for i in range(3):
            client.post(
                "/api/v1/intake/leads/ingest",
                json={
                    **base_payload,
                    "first_name": f"Lead{i}",
                    "last_name": "Test",
                    "email": f"lead{i}@example.com",
                },
                headers=headers,
            )

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


def test_ingest_lead_endpoint_negative_budget_is_accepted_and_rejected_in_the_tray():
    tenant_id = str(uuid.uuid4())
    payload = {
        "first_name": "Bad",
        "last_name": "Budget",
        "email": "bad.budget@example.com",
        "company": "Corp",
        "budget": -100.0,
        "industry": "Tech",
    }

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        record = ingest_and_resolve(client, headers, payload)

        # The hinge of this phase: a payload that fails validation is still
        # persisted, not lost — it lands as a REJECTED IntakeRecord with its
        # detail, instead of vanishing behind a synchronous error response.
        assert record["id"]
        assert record["status"] == "REJECTED"
        assert record["errors"][0]["error_code"] == "INVALID_BUDGET"


def test_list_leads_filters_by_status_and_total_reflects_the_filter():
    # The central assertion of the filters task: total/has_more must come
    # from the filtered count, not the tenant's whole pipeline.
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        agent_headers, agent_id = _agent_auth_headers(tenant_id)

        assigned = ingest_and_resolve(client, headers, {
            "first_name": "Ana", "last_name": "Soto", "email": "ana@filters.test",
            "company": "FiltersCo", "budget": 1000.0, "industry": "Tech",
        })
        other = ingest_and_resolve(client, headers, {
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
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads?status=BASURA", headers=headers)
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_LEAD_STATUS"


def test_list_leads_search_finds_by_company_and_excludes_others():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        match = ingest_and_resolve(client, headers, {
            "first_name": "Carlos", "last_name": "Diaz", "email": "carlos@search.test",
            "company": "UniqueCorpXYZ", "budget": 1000.0, "industry": "Tech",
        })
        ingest_and_resolve(client, headers, {
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
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        group_id = _create_group(tenant_id)
        _, agent_one = _agent_auth_headers(tenant_id, group_id=group_id)
        _, agent_two = _agent_auth_headers(tenant_id, group_id=group_id)

        lead_one = ingest_and_resolve(client, headers, {
            "first_name": "Eva", "last_name": "Ruiz", "email": "eva@group.test",
            "company": "GroupCo", "budget": 1000.0, "industry": "Tech",
        })
        lead_two = ingest_and_resolve(client, headers, {
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
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        target = ingest_and_resolve(client, headers, {
            "first_name": "Gia", "last_name": "Nova", "email": "gia@combo.test",
            "company": "ComboMatchCo", "budget": 1000.0, "industry": "Tech",
        })
        client.post(
            f"/api/v1/leads/{target['lead_id']}/discard",
            json={"reason": "No cumple criterios"},
            headers=headers,
        )
        # Same company, but never discarded: matches q alone, not both filters together.
        ingest_and_resolve(client, headers, {
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
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        agent_headers, agent_id = _agent_auth_headers(tenant_id)
        _, other_agent_id = _agent_auth_headers(tenant_id)

        mine = ingest_and_resolve(client, headers, {
            "first_name": "Ivan", "last_name": "Solis", "email": "ivan@mine.test",
            "company": "MineCo", "budget": 1000.0, "industry": "Tech",
        })
        colleague_lead = ingest_and_resolve(client, headers, {
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
        _seed_tenant_with_sources(tenant_a)
        _seed_tenant_with_sources(tenant_b)
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        ingest_and_resolve(client, headers_b, {
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
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/leads/stats", headers=headers)

        assert response.status_code == 200
        assert "by_status" in response.json()


def test_lead_stats_returns_the_five_adr_keys_and_stays_internally_consistent():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        group_id = _create_group(tenant_id)
        agent_headers, agent_id = _agent_auth_headers(tenant_id, group_id=group_id)

        assigned = ingest_and_resolve(client, headers, {
            "first_name": "Lea", "last_name": "Funes", "email": "lea@stats.test",
            "company": "StatsCo", "budget": 1000.0, "industry": "Tech",
        })
        client.post(f"/api/v1/leads/{assigned['lead_id']}/assign", json={"agent_id": agent_id}, headers=headers)

        response = client.get("/api/v1/leads/stats", headers=headers)

        assert response.status_code == 200
        body = response.json()
        for key in ("total", "by_status", "unassigned", "pending_intake", "load_by_agent"):
            assert key in body
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
        _seed_tenant_with_sources(tenant_a)
        _seed_tenant_with_sources(tenant_b)
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        ingest_and_resolve(client, headers_b, {
            "first_name": "Otto", "last_name": "Vera", "email": "otto@other-org.test",
            "company": "OtherOrgCo", "budget": 1000.0, "industry": "Tech",
        })

        response = client.get("/api/v1/leads/stats", headers=headers_a)

        assert response.status_code == 200
        assert response.json()["total"] == 0


def test_lead_stats_forbidden_for_agent_and_platform_admin():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        agent_headers, _ = _agent_auth_headers(tenant_id)
        admin_headers = _admin_auth_headers()

        assert client.get("/api/v1/leads/stats", headers=agent_headers).status_code == 403
        assert client.get("/api/v1/leads/stats", headers=admin_headers).status_code == 403


def test_lead_stats_rejects_a_from_later_than_to():
    tenant_id = str(uuid.uuid4())
    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        response = client.get(
            "/api/v1/leads/stats?from=2030-01-01&to=2020-01-01", headers=headers,
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_DATE_RANGE"
