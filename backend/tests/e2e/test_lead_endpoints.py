import uuid
from fastapi.testclient import TestClient
from infrastructure.main import app

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
        client.post(f"/api/v1/tenants/{tenant_id}/leads/ingest", json=payload)

        response = client.get(f"/api/v1/tenants/{tenant_id}/leads")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["email"] == "laura@example.com"

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
