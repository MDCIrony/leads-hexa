import uuid
from typing import Optional

from domain.entities.lead import Lead
from domain.entities.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind, LeadStatus
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import (
    RawSqlLeadRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)

_TENANT = uuid.uuid4()


def _seed_source(conn, tenant_id: uuid.UUID) -> uuid.UUID:
    """leads.source_id is a real foreign key (migration 005): an invented
    UUID is rejected, so every test needs a persisted source of its own."""
    source = RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant_id, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
    )
    return source.id.value


def _lead(email: str, source_id: uuid.UUID, tenant_id: Optional[uuid.UUID] = None) -> Lead:
    return Lead.create(
        tenant_id=tenant_id or _TENANT, source_id=source_id, first_name="Ana", last_name="Diaz",
        email=email, company="Acme", budget=1000, industry="tech",
        status=LeadStatus.QUALIFIED,
    )


def test_the_assignment_trace_survives_a_round_trip(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        source_id = _seed_source(conn, _TENANT)
        agent = uuid.uuid4()
        lead = _lead(f"trace-{uuid.uuid4()}@x.test", source_id)
        lead.assign_to(agent, _TENANT)
        repo.save(lead)

        stored = repo.get_by_id(lead.id.value)

        assert stored.status == LeadStatus.ASSIGNED
        assert stored.assigned_agent_id.value == agent
        assert stored.assigned_at is not None


def test_a_discarded_lead_keeps_its_reason(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        source_id = _seed_source(conn, _TENANT)
        lead = _lead(f"disc-{uuid.uuid4()}@x.test", source_id)
        lead.discard("duplicado")
        repo.save(lead)

        stored = repo.get_by_id(lead.id.value)

        assert stored.status == LeadStatus.DISCARDED
        assert stored.discard_reason == "duplicado"


def test_an_agent_only_sees_their_own_leads(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        tenant = uuid.uuid4()
        source_id = _seed_source(conn, tenant)
        mine, theirs = uuid.uuid4(), uuid.uuid4()

        a = _lead(f"mine-{uuid.uuid4()}@x.test", source_id, tenant); a.assign_to(mine, tenant); repo.save(a)
        b = _lead(f"theirs-{uuid.uuid4()}@x.test", source_id, tenant); b.assign_to(theirs, tenant); repo.save(b)

        found = repo.list_by_agent(tenant, mine)

        assert [str(l.email) for l in found] == [str(a.email)]
        assert repo.count_by_agent(tenant, mine) == 1


def test_reading_a_lead_of_another_organization_returns_nothing(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        source_id = _seed_source(conn, _TENANT)
        lead = _lead(f"other-{uuid.uuid4()}@x.test", source_id)
        repo.save(lead)

        assert repo.get_by_id_and_tenant(lead.id.value, _TENANT) is not None
        assert repo.get_by_id_and_tenant(lead.id.value, uuid.uuid4()) is None
