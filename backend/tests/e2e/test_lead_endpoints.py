import os
import uuid
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from domain.value_objects.enums import AgentRole


def _get_auth_headers() -> dict:
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from domain.entities.agent import Agent

    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
    db = app.state.db
    uow = PostgresUnitOfWork(db)
    with uow:
        active_agents = uow.agents.list_active()
        if active_agents:
            admin_agent = active_agents[0]
            admin_agent.role = AgentRole.ADMIN
            uow.agents.save(admin_agent)
            admin_token = token_service.issue(TokenClaims(agent_id=str(admin_agent.id), role="ADMIN", tenant_id=None))
            return {"Authorization": f"Bearer {admin_token}"}
        else:
            agent = Agent.create(
                name="Admin",
                email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
                team="Admin",
                role=AgentRole.ADMIN,
            )
            uow.agents.save(agent)
            admin_token = token_service.issue(TokenClaims(agent_id=str(agent.id), role="ADMIN", tenant_id=None))
            return {"Authorization": f"Bearer {admin_token}"}


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
        response = client.post(f"/api/v1/tenants/{tenant_id}/leads/ingest", json=payload)
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
        response = client.post(f"/api/v1/tenants/{tenant_id}/leads/ingest", json=payload)
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
        response = client.post(f"/api/v1/tenants/{tenant_id}/leads/batch-upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["total_rows"] == 2
        assert data["successful_ingestions"] == 2

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
        headers = _get_auth_headers()
        client.post(f"/api/v1/tenants/{tenant_id}/leads/ingest", json=payload)

        response = client.get(f"/api/v1/tenants/{tenant_id}/leads", headers=headers)
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
        headers = _get_auth_headers()
        for i in range(3):
            client.post(
                f"/api/v1/tenants/{tenant_id}/leads/ingest",
                json={
                    **base_payload,
                    "first_name": f"Lead{i}",
                    "last_name": "Test",
                    "email": f"lead{i}@example.com",
                },
            )

        response = client.get(f"/api/v1/tenants/{tenant_id}/leads?limit=2&offset=0", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["has_more"] is True

        response = client.get(f"/api/v1/tenants/{tenant_id}/leads?limit=2&offset=2", headers=headers)
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
        response = client.post(f"/api/v1/tenants/{tenant_id}/leads/ingest", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert data["error_code"] == "INVALID_BUDGET"
        assert "message" in data
