"""GET /api/v1/intake/stats: the inbox's own counters, manager only like /leads/stats."""
import uuid

from domain.entities.intake_record import IntakeRecord
from infrastructure.adapters.output.persistence.raw_sql_intake_record_repository import RawSqlIntakeRecordRepository
from infrastructure.main import app
from tests.e2e._intake_helpers import ingest_and_resolve
from tests.e2e.auth_helpers import agent_of, seed_org_manager
from tests.e2e.gateway_client import GatewayClient, tenant_of

_LEAD = {"first_name": "Ana", "last_name": "Diaz", "company": "Acme", "budget": 1000, "industry": "tech"}


def _seed_pending(manager: dict, source_id: str) -> None:
    """A record no job has picked up yet: the gateway client drains every job it queues."""
    with app.state.container.database.get_connection(autocommit=True) as conn:
        RawSqlIntakeRecordRepository(conn).save(IntakeRecord.create(
            tenant_id=tenant_of(manager), source_id=source_id, payload={}))


def test_the_manager_sees_pending_rejected_and_their_sum(test_db):
    with GatewayClient(app) as client:
        manager = seed_org_manager()
        rejected = ingest_and_resolve(client, manager, {**_LEAD, "email": "not-an-email"})
        ingest_and_resolve(client, manager, {**_LEAD, "email": "ana@x.test"})
        _seed_pending(manager, rejected["source_id"])
        _seed_pending(manager, rejected["source_id"])

        response = client.get("/api/v1/intake/stats", headers=manager)

    assert response.status_code == 200, response.text
    assert response.json() == {"pending": 2, "rejected": 1, "pending_intake": 3}


def test_an_agent_is_refused_like_on_lead_stats(test_db):
    with GatewayClient(app) as client:
        agent, _ = agent_of(seed_org_manager())

        response = client.get("/api/v1/intake/stats", headers=agent)
        lead_stats = client.get("/api/v1/leads/stats", headers=agent)

    assert response.status_code == lead_stats.status_code == 403


def test_another_organization_does_not_count_the_first_ones_records(test_db):
    with GatewayClient(app) as client:
        first, second = seed_org_manager(), seed_org_manager()
        ingest_and_resolve(client, first, {**_LEAD, "email": "bad"})

        response = client.get("/api/v1/intake/stats", headers=second)

    assert response.json() == {"pending": 0, "rejected": 0, "pending_intake": 0}
    assert uuid.UUID(tenant_of(first)) != uuid.UUID(tenant_of(second))
