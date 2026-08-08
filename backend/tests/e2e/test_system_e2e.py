import os
import uuid
from typing import Tuple

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService

from _intake_helpers import ingest_and_resolve


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


def _create_tenant_and_manager_headers(client: TestClient, admin_headers: dict) -> Tuple[str, dict]:
    """Rules and lead listing scope to the caller's own tenant (from the
    token), so driving a tenant's routing flow now requires a real
    organization created through the platform plane, with a Manager
    persisted for it, rather than a made-up tenant_id and the tenant-less
    bootstrap Admin."""
    manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post(
        "/api/v1/tenants",
        json={
            "name": f"Org {uuid.uuid4().hex[:6]}",
            "manager": {"name": "Org Manager", "email": manager_email, "password": "manager-pass-123"},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    tenant_id = resp.json()["id"]

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": manager_email, "password": "manager-pass-123"},
    )
    assert login_resp.status_code == 200
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    return tenant_id, headers


def test_full_system_lead_routing_flow_e2e():
    """
    Prueba E2E completa del sistema:
    1. Crea un agente disponible.
    2. Configura regla de scoring (+35 pts por budget > 10000).
    3. Configura regla de asignación (min_score: 30 -> apunta directo al agente).
    4. Ingesta un Lead con budget 15000.
    5. Verifica que el lead resulte ASSIGNED con score 35 y asignado al agente.
    """
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        _, headers = _create_tenant_and_manager_headers(client, admin_headers)

        # 1. Crear agente
        agent_payload = {
            "name": "Carlos Lopez",
            "email": "clopez@sales.com",
            "is_active": True,
            "password": "test-password-123",
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

        # 3. Crear regla de asignación (apunta directo al agente, sin grupo)
        assignment_resp = client.post(
            "/api/v1/rules/assignment",
            json={
                "name": "Sales band",
                "min_score": 30,
                "strategy": "LOWEST_LOAD",
                "target_agent_ids": [agent_id],
            },
            headers=headers,
        )
        assert assignment_resp.status_code == 201


        # 4. Ingestar Lead
        record = ingest_and_resolve(
            client,
            headers,
            {
                "first_name": "Maria",
                "last_name": "Gomez",
                "email": "mgomez@techcorp.com",
                "company": "TechCorp Inc",
                "budget": 15000.0,
                "industry": "Technology",
                "custom_attributes": {"employee_count": 150},
            },
        )
        lead_resp = client.get(f"/api/v1/leads/{record['lead_id']}", headers=headers)
        assert lead_resp.status_code == 200
        result = lead_resp.json()

        # 5. Verificaciones
        assert result["status"] == "ASSIGNED"
        assert result["score"] == 35
        assert result["assigned_agent_id"] == agent_id

        # 6. El agente sigue existiendo y activo; su carga ya no se expone en
        # el propio agente (active_leads_count desapareció), se deriva de sus
        # leads asignados — cubierto por la aserción anterior.
        updated_agent = client.get(f"/api/v1/agents/{agent_id}", headers=headers).json()
        assert updated_agent["is_active"] is True
