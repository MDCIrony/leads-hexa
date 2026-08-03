import uuid
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from domain.entities.lead import Lead
from domain.value_objects import LeadStatus

def test_raw_sql_lead_repository_lifecycle():
    db = RawSqlDatabase(":memory:")
    db.init_db()

    connection = db.get_connection()
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
