import os
import uuid
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService


def _bootstrap_admin_headers(client: TestClient) -> dict:
    """The agents table is empty at the start of every e2e test (see
    clean_tables), so the first unauthenticated POST always rides the
    bootstrap rule and becomes Admin."""
    resp = client.post(
        "/api/v1/agents",
        json={
            "name": "Bootstrap Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@test.com",
            "team": "HQ",
            "password": "bootstrap-pass-123",
        },
    )
    assert resp.status_code == 201
    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
    token = token_service.issue(TokenClaims(agent_id=resp.json()["id"], role="ADMIN", tenant_id=None))
    return {"Authorization": f"Bearer {token}"}


def _manager_headers_for(client: TestClient, admin_headers: dict, tenant_id: str) -> dict:
    """Rules and lead listing scope to the caller's own tenant (from the
    token), so driving a tenant's routing flow now requires a Manager
    persisted for that tenant rather than the tenant-less bootstrap Admin."""
    resp = client.post(
        "/api/v1/agents",
        json={
            "name": "Org Manager",
            "email": f"manager_{uuid.uuid4().hex[:6]}@test.com",
            "team": "Sales",
            "password": "manager-pass-123",
            "role": "MANAGER",
            "tenant_id": tenant_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
    token = token_service.issue(TokenClaims(agent_id=resp.json()["id"], role="MANAGER", tenant_id=tenant_id))
    return {"Authorization": f"Bearer {token}"}


def test_full_system_lead_routing_flow_e2e():
    """
    Prueba E2E completa del sistema:
    1. Crea un agente disponible.
    2. Configura regla de scoring (+35 pts por budget > 10000).
    3. Configura regla de routing (min_score: 30 -> asigna a equipo Sales).
    4. Ingesta un Lead con budget 15000.
    5. Verifica que el lead resulte ASSIGNED con score 35 y asignado al agente.
    """
    tenant_id = str(uuid.uuid4())

    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        headers = _manager_headers_for(client, admin_headers, tenant_id)

        # 1. Crear agente
        agent_payload = {
            "name": "Carlos Lopez",
            "email": "clopez@sales.com",
            "team": "Sales",
            "active_leads_count": 0,
            "is_active": True,
            "password": "test-password-123",
            "tenant_id": tenant_id,
        }
        agent_resp = client.post("/api/v1/agents", json=agent_payload, headers=headers)
        assert agent_resp.status_code == 201
        agent_data = agent_resp.json()
        agent_id = agent_data["id"]

        # 2. Crear regla de scoring
        scoring_resp = client.post(
            "/api/v1/rules/scoring",
            json={
                "name": "High Budget Bonus",
                "field": "budget",
                "operator": "GREATER_THAN",
                "value": 10000,
                "score_delta": 35,
            },
            headers=headers,
        )
        assert scoring_resp.status_code == 201

        # 3. Crear regla de routing
        routing_resp = client.post(
            "/api/v1/rules/routing",
            json={
                "min_score": 30,
                "target_team": "Sales",
                "assignment_strategy": "LOWEST_LOAD",
                "target_agent_ids": [agent_id],
            },
            headers=headers,
        )
        assert routing_resp.status_code == 201


        # 4. Ingestar Lead
        ingest_resp = client.post(
            f"/api/v1/intake/{tenant_id}/leads/ingest",
            json={
                "first_name": "Maria",
                "last_name": "Gomez",
                "email": "mgomez@techcorp.com",
                "company": "TechCorp Inc",
                "budget": 15000.0,
                "industry": "Technology",
                "custom_attributes": {"employee_count": 150},
            },
        )
        assert ingest_resp.status_code == 201
        result = ingest_resp.json()

        # 5. Verificaciones
        assert result["status"] == "ASSIGNED"
        assert result["score"] == 35
        assert result["assigned_agent_id"] == agent_id

        # 6. Verificar actualización de agente
        updated_agent = client.get(f"/api/v1/agents/{agent_id}", headers=headers).json()
        assert updated_agent["active_leads_count"] == 1
