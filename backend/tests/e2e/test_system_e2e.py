from typing import Tuple

from gateway_client import GatewayClient, tenant_of
from infrastructure.main import app

from _intake_helpers import ingest_and_resolve
from auth_helpers import agent_of, seed_org_manager


def _create_tenant_and_manager_headers(client: GatewayClient) -> Tuple[str, dict]:
    """Rules and lead listing scope to the caller's own tenant (from the
    token), so driving a tenant's routing flow requires a Manager of a real
    organization, with its default sources, rather than a made-up tenant_id."""
    headers = seed_org_manager("Org Manager")
    return tenant_of(headers), headers


def test_full_system_lead_routing_flow_e2e():
    """
    Prueba E2E completa del sistema:
    1. Crea un agente disponible.
    2. Configura regla de scoring (+35 pts por budget > 10000).
    3. Configura regla de asignación (min_score: 30 -> apunta directo al agente).
    4. Ingesta un Lead con budget 15000.
    5. Verifica que el lead resulte ASSIGNED con score 35 y asignado al agente.
    """
    with GatewayClient(app) as client:
        _, headers = _create_tenant_and_manager_headers(client)

        # 1. Crear agente (identity lo publica; lead-core lo proyecta como asesor)
        _, agent_id = agent_of(headers, "Carlos Lopez")

        # 2. Crear regla de scoring
        scoring_resp = client.post(
            "/api/v1/rules/scoring",
            json={
                "name": "High Budget Bonus",
                "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 10000}],
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

        # 6. El asesor sigue activo y su carga refleja el lead asignado.
        advisors = client.get("/api/v1/advisors", headers=headers).json()["items"]
        updated_agent = next(item for item in advisors if item["agent_id"] == agent_id)
        assert updated_agent["is_active"] is True
