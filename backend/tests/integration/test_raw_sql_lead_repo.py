import uuid
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)
from domain.entities.lead import Lead
from domain.entities.lead_source import LeadSource
from domain.value_objects import LeadStatus
from domain.value_objects.enums import LeadSourceKind


def _seed_source(connection, tenant_id: uuid.UUID) -> uuid.UUID:
    """leads.tenant_id and leads.source_id are real foreign keys (migration
    005): an invented UUID is rejected, so every test needs a persisted
    organization and source of its own."""
    connection.execute(
        "INSERT INTO tenants (id, name, slug, created_at) VALUES (%s, %s, %s, now())",
        (tenant_id, "Acme", f"acme-{tenant_id}"),
    )
    source = RawSqlLeadSourceRepository(connection).save(
        LeadSource.create(tenant_id=tenant_id, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
    )
    return source.id.value


def test_raw_sql_lead_repository_lifecycle(test_db):
    with test_db.get_connection() as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        lead = Lead.create(
            tenant_id=tenant_id,
            source_id=source_id,
            first_name="Maria",
            last_name="Gomez",
            email="mgomez@techcorp.com",
            company="TechCorp Inc",
            budget=15000,
            industry="Technology",
            custom_attributes={"employee_count": 150},
            lead_id=lead_id,
        )
        lead.apply_score(45)
        lead.status = LeadStatus.QUALIFIED

        repo.save(lead)
        connection.commit()

        fetched = repo.get_by_id(lead_id)
        assert fetched is not None
        assert str(fetched.id) == str(lead_id)
        assert str(fetched.email) == "mgomez@techcorp.com"
        assert float(fetched.budget) == 15000.0
        assert int(fetched.score) == 45
        assert fetched.status == LeadStatus.QUALIFIED
        assert fetched.custom_attributes == {"employee_count": 150}

        tenant_leads = repo.list_by_tenant(tenant_id)
        assert len(tenant_leads) == 1


def test_a_lead_without_an_email_round_trips_as_none(test_db):
    """str(lead.email) used to turn a missing email into the literal string
    "None" on save; this guards the fix at the persistence boundary."""
    with test_db.get_connection() as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        lead = Lead.create(
            tenant_id=tenant_id,
            source_id=source_id,
            first_name="Luis",
            last_name="Nogales",
            email=None,
            company="Acme",
            budget=500,
            industry="Retail",
            lead_id=lead_id,
        )

        repo.save(lead)
        connection.commit()

        fetched = repo.get_by_id(lead_id)
        assert fetched is not None
        assert fetched.email is None


def _lead_for_load_test(tenant_id: uuid.UUID, source_id: uuid.UUID, email: str) -> Lead:
    # QUALIFIED, not the NEW default: assign_to below requires a lead that is
    # actually assignable, and every caller of this helper assigns it.
    return Lead.create(
        tenant_id=tenant_id,
        source_id=source_id,
        first_name="Laura",
        last_name="Diaz",
        email=email,
        company="Globex",
        budget=1000,
        industry="Tech",
        status=LeadStatus.QUALIFIED,
    )


def test_active_load_by_agent_counts_only_currently_assigned_leads(test_db):
    """Derived on read: three leads land on Ana, one on Beto, and neither the
    unassigned lead nor the disqualified one (despite still carrying an
    assigned_agent_id) should count."""
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)
        ana, beto = uuid.uuid4(), uuid.uuid4()

        for i in range(3):
            lead = _lead_for_load_test(tenant_id, source_id, f"ana{i}@example.com")
            lead.assign_to(ana, lead.tenant_id)
            repo.save(lead)

        lead = _lead_for_load_test(tenant_id, source_id, "beto@example.com")
        lead.assign_to(beto, lead.tenant_id)
        repo.save(lead)

        unassigned = _lead_for_load_test(tenant_id, source_id, "unassigned@example.com")
        repo.save(unassigned)

        # Simulates a lead disqualified after assignment: assigned_agent_id
        # stays set while status moves away from ASSIGNED, which is exactly
        # the case active_load_by_agent must not be fooled by.
        disqualified = _lead_for_load_test(tenant_id, source_id, "disqualified@example.com")
        disqualified.assign_to(ana, disqualified.tenant_id)
        disqualified.status = LeadStatus.DISQUALIFIED
        repo.save(disqualified)

        loads = repo.active_load_by_agent(tenant_id)

        assert loads == {ana: 3, beto: 1}
