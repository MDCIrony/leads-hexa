import os
import uuid

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from domain.value_objects.enums import AgentRole, IntakeRecordStatus, LeadSourceKind


def _manager_auth_headers(tenant_id: str) -> dict:
    """`list_leads` now scopes to the caller's own tenant, taken from the
    verified token, so listing a given tenant's leads requires a Manager
    persisted for that tenant rather than a tenant-less Admin."""
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from domain.entities.agent import Agent

    db = app.state.container.database
    uow = PostgresUnitOfWork(db)
    manager = Agent.create(
        name="Manager",
        email=f"manager_{uuid.uuid4().hex[:6]}@test.com",
        role=AgentRole.MANAGER,
        tenant_id=tenant_id,
    )
    with uow:
        uow.agents.save(manager)

    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
    token = token_service.issue(
        TokenClaims(agent_id=str(manager.id), role="MANAGER", tenant_id=str(tenant_id))
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_tenant_with_sources(tenant_id: str) -> None:
    """leads.tenant_id and leads.source_id are now real foreign keys, and the
    intake router resolves the source itself (migration 005), so every ingest
    test needs a persisted tenant with its two default sources instead of a
    bare UUID that merely looks like one."""
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from domain.entities.lead_source import LeadSource

    db = app.state.container.database
    uow = PostgresUnitOfWork(db)
    with uow:
        uow.connection.execute(
            "INSERT INTO tenants (id, name, slug, created_at) VALUES (%s, %s, %s, now())",
            (tenant_id, "Acme", f"acme-{tenant_id}"),
        )
        uow.sources.save(
            LeadSource.create(tenant_id=tenant_id, name="Formulario manual", kind=LeadSourceKind.MANUAL_FORM)
        )
        uow.sources.save(
            LeadSource.create(tenant_id=tenant_id, name="Carga de fichero", kind=LeadSourceKind.FILE_UPLOAD)
        )


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

    with TestClient(app) as client:
        # The connection pool only exists inside the TestClient lifespan
        # (opened on FastAPI startup, closed on shutdown), so seeding must
        # happen after entering this block, not before it.
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert "lead_id" in data
        assert data["status"] in ("NEW", "QUALIFIED", "DISQUALIFIED", "ASSIGNED")
        assert "score" in data

def test_ingest_lead_endpoint_invalid_email_validation():
    tenant_id = str(uuid.uuid4())
    payload = {
        "first_name": "Maria",
        "last_name": "Gomez",
        "email": "email-sin-arroba",
        "company": "TechCorp Inc",
        "budget": 15000.0,
        "industry": "Technology"
    }

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)
        assert response.status_code == 422

def test_batch_upload_endpoint():
    tenant_id = str(uuid.uuid4())
    csv_content = (
        "first_name,last_name,email,company,budget,industry\n"
        "Ana,Silva,ana@company.com,CompanyA,20000,Finance\n"
        "Luis,Perez,luis@company.com,CompanyB,10000,Retail\n"
    ).encode("utf-8")

    files = {"file": ("leads.csv", csv_content, "text/csv")}

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/batch-upload", files=files, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["total_rows"] == 2
        assert data["successful_ingestions"] == 2

def test_batch_upload_reports_failed_rows_without_losing_the_valid_ones():
    tenant_id = str(uuid.uuid4())
    csv_content = (
        "first_name,last_name,email,company,budget,industry\n"
        "Ana,Silva,ana@company.com,CompanyA,20000,Finance\n"
        "Mal,Formado,email-sin-arroba,CompanyB,10000,Retail\n"
        "Luis,Perez,luis@company.com,CompanyC,10000,Retail\n"
    ).encode("utf-8")

    files = {"file": ("leads.csv", csv_content, "text/csv")}

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/batch-upload", files=files, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 3
        assert data["successful_ingestions"] == 2
        assert len(data["failed_rows"]) == 1

        failed = data["failed_rows"][0]
        assert failed["row_number"] == 2
        assert failed["email"] == "email-sin-arroba"
        assert failed["error_code"] == "INVALID_EMAIL"

        # The row must say WHERE it was kept, not just that it failed. Without
        # this the manager has to pair the response against the inbox by
        # matching contents, which is ambiguous as soon as two rows look alike.
        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
        uow = PostgresUnitOfWork(app.state.container.database)
        assert failed["intake_record_id"]
        with uow:
            record = uow.intake_records.get_by_id_and_tenant(
                uuid.UUID(failed["intake_record_id"]), uuid.UUID(tenant_id)
            )
        assert record is not None
        assert record.status.value == "REJECTED"

        # A bad row must not drag the good ones down with it: only the 2
        # valid rows are actually persisted for this tenant.
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

    with TestClient(app) as client:
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

    with TestClient(app) as client:
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


def test_ingest_lead_endpoint_negative_budget_returns_400():
    tenant_id = str(uuid.uuid4())
    payload = {
        "first_name": "Bad",
        "last_name": "Budget",
        "email": "bad.budget@example.com",
        "company": "Corp",
        "budget": -100.0,
        "industry": "Tech",
    }

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)
        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert data["error_code"] == "INVALID_BUDGET"
        assert "message" in data
        assert data["intake_record_id"]

        # The hinge of this phase: a payload that fails validation is still
        # persisted, not lost — it lands as a REJECTED IntakeRecord instead
        # of vanishing behind a 400.
        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
        uow = PostgresUnitOfWork(app.state.container.database)
        with uow:
            record = uow.intake_records.get_by_id_and_tenant(
                uuid.UUID(data["intake_record_id"]), uuid.UUID(tenant_id)
            )
        assert record is not None
        assert record.status == IntakeRecordStatus.REJECTED
