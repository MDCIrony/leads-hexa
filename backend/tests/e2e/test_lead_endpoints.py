import os
import uuid
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
# `infrastructure.main` reads Settings at module level (for CORS), so
# DATABASE_URL must exist by import time, not just by app startup.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5433/leads_test")

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from domain.value_objects.enums import AgentRole


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
        response = client.post(f"/api/v1/intake/{tenant_id}/leads/ingest", json=payload)
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
        response = client.post(f"/api/v1/intake/{tenant_id}/leads/ingest", json=payload)
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
        response = client.post(f"/api/v1/intake/{tenant_id}/leads/batch-upload", files=files)
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
        response = client.post(f"/api/v1/intake/{tenant_id}/leads/batch-upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 3
        assert data["successful_ingestions"] == 2
        assert len(data["failed_rows"]) == 1

        failed = data["failed_rows"][0]
        assert failed["row_number"] == 2
        assert failed["email"] == "email-sin-arroba"
        assert failed["error_code"] == "INVALID_EMAIL"

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

    with TestClient(app) as client:
        headers = _manager_auth_headers(tenant_id)
        client.post(f"/api/v1/intake/{tenant_id}/leads/ingest", json=payload)

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
        headers = _manager_auth_headers(tenant_id)
        for i in range(3):
            client.post(
                f"/api/v1/intake/{tenant_id}/leads/ingest",
                json={
                    **base_payload,
                    "first_name": f"Lead{i}",
                    "last_name": "Test",
                    "email": f"lead{i}@example.com",
                },
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
        response = client.post(f"/api/v1/intake/{tenant_id}/leads/ingest", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert data["error_code"] == "INVALID_BUDGET"
        assert "message" in data
