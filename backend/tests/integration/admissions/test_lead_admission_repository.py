"""RawSqlLeadRepository's side of idempotent admission."""
from uuid import uuid4

import pytest

from application.ports.output.lead_repository_port import DuplicateAdmission
from domain.entities.lead import Lead
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository


def _lead(tenant_id, intake_record_id=None) -> Lead:
    return Lead.create(tenant_id=tenant_id, source_id=uuid4(), first_name="A", last_name="B", company="C",
                       budget="10", industry="D", intake_record_id=intake_record_id)


def test_the_link_round_trips_and_is_found_by_record(test_db):
    tenant, record = uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        lead = repo.save(_lead(tenant, record))

        found = repo.get_by_intake_record(tenant, record)

        assert (found.id, found.intake_record_id) == (lead.id, record)
        assert repo.get_by_intake_record(uuid4(), record) is None


def test_a_second_lead_for_the_same_record_is_a_duplicate_admission(test_db):
    tenant, record = uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        repo.save(_lead(tenant, record))

        with pytest.raises(DuplicateAdmission):
            repo.save(_lead(tenant, record))


def test_updating_a_lead_keeps_its_link(test_db):
    tenant, record = uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        lead = repo.save(_lead(tenant, record))
        lead.qualify()
        repo.save(lead)

        assert repo.get_by_id(lead.id.value).intake_record_id == record


def test_the_lookup_lists_the_known_records_across_organizations(test_db):
    first, second = (uuid4(), uuid4()), (uuid4(), uuid4())
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlLeadRepository(conn)
        leads = [repo.save(_lead(tenant, record)) for tenant, record in (first, second)]

        items = repo.list_by_intake_records([first[1], second[1], uuid4()])

        assert sorted((i.intake_record_id, i.tenant_id, i.lead_id) for i in items) == sorted(
            (str(record), str(tenant), str(lead.id)) for (tenant, record), lead in zip((first, second), leads))
