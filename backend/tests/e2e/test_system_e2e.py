import os
import uuid
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from domain.value_objects.enums import AgentRole

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
        # 1. Crear agente
        headers = {}
        agent_payload = {
            "name": "Carlos Lopez",
            "email": "clopez@sales.com",
            "team": "Sales",
            "active_leads_count": 0,
            "is_active": True,
            "password": "test-password-123",
        }
        agent_resp = client.post("/api/v1/agents", json=agent_payload, headers=headers)
        if agent_resp.status_code == 401:
            from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
            db = app.state.db
            uow = PostgresUnitOfWork(db)
            with uow:
                active_agents = uow.agents.list_active()
                if active_agents:
                    admin_agent = active_agents[0]
                    admin_agent.role = AgentRole.ADMIN
                    uow.agents.save(admin_agent)
                    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
                    admin_token = token_service.issue(TokenClaims(agent_id=str(admin_agent.id), role="ADMIN", tenant_id=None))
                    headers = {"Authorization": f"Bearer {admin_token}"}
                    agent_resp = client.post("/api/v1/agents", json=agent_payload, headers=headers)

        assert agent_resp.status_code == 201
        agent_data = agent_resp.json()
        agent_id = agent_data["id"]

        if not headers:
            token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
            admin_token = token_service.issue(TokenClaims(agent_id=agent_id, role="ADMIN", tenant_id=None))
            headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Crear regla de scoring
        scoring_resp = client.post(
            f"/api/v1/tenants/{tenant_id}/rules/scoring",
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
            f"/api/v1/tenants/{tenant_id}/rules/routing",
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
            f"/api/v1/tenants/{tenant_id}/leads/ingest",
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

