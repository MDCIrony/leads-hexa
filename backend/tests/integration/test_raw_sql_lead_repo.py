import uuid
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from domain.entities.lead import Lead
from domain.value_objects import LeadStatus

def test_raw_sql_lead_repository_lifecycle():
    db = RawSqlDatabase()
    db.init_db()

    with db.get_connection() as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        lead = Lead.create(
            tenant_id=tenant_id,
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


def _lead_for_load_test(tenant_id: uuid.UUID, email: str) -> Lead:
    return Lead.create(
        tenant_id=tenant_id,
        first_name="Laura",
        last_name="Diaz",
        email=email,
        company="Globex",
        budget=1000,
        industry="Tech",
    )


def test_active_load_by_agent_counts_only_currently_assigned_leads(test_db):
    """Derived on read: three leads land on Ana, one on Beto, and neither the
    unassigned lead nor the disqualified one (despite still carrying an
    assigned_agent_id) should count."""
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        ana, beto = uuid.uuid4(), uuid.uuid4()

        for i in range(3):
            lead = _lead_for_load_test(tenant_id, f"ana{i}@example.com")
            lead.assign_to_agent(ana)
            repo.save(lead)

        lead = _lead_for_load_test(tenant_id, "beto@example.com")
        lead.assign_to_agent(beto)
        repo.save(lead)

        unassigned = _lead_for_load_test(tenant_id, "unassigned@example.com")
        repo.save(unassigned)

        disqualified = _lead_for_load_test(tenant_id, "disqualified@example.com")
        disqualified.assign_to_agent(ana)
        disqualified.status = LeadStatus.DISQUALIFIED
        repo.save(disqualified)

        loads = repo.active_load_by_agent(tenant_id)

        assert loads == {ana: 3, beto: 1}
