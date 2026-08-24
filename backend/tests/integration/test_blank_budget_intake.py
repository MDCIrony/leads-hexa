from uuid import uuid4

import psycopg
import pytest

from application.use_cases.ingest_lead_use_case import command_from_record, payload_of
from domain.entities.intake_record import IntakeRecord
from domain.entities.lead import Lead
from domain.entities.lead_source import LeadSource
from domain.entities.tenant import Tenant
from domain.exceptions import InvalidBudgetException
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.raw_sql_intake_record_repository import (
    RawSqlIntakeRecordRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)

_CSV_WITH_A_BLANK_BUDGET = b"""first_name,last_name,email,company,budget,industry
Juan,Perez,jperez@smallbiz.es,SmallBiz Local,,Retail
"""


def _tenant(conn: psycopg.Connection) -> Tenant:
    # A real row is required: intake_records.tenant_id has a foreign key to
    # tenants (migration 005).
    return RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))


def _source(conn: psycopg.Connection, tenant_id) -> LeadSource:
    return RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(
            tenant_id=tenant_id, name=f"Fuente {uuid4()}", kind=LeadSourceKind.FILE_UPLOAD
        )
    )


def test_a_blank_budget_cell_still_persists_its_intake_record(test_db):
    """The whole point of ADR-0009: what arrives is stored before anything
    tries to interpret it. A NaN budget used to make this insert fail, taking
    every other row of the batch down with it."""
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        commands = PandasFileParser().parse_leads_file(
            _CSV_WITH_A_BLANK_BUDGET, "leads.csv", tenant.id.value, source.id.value
        )

        repo = RawSqlIntakeRecordRepository(conn)
        saved = repo.save(
            IntakeRecord.create(
                tenant_id=tenant.id.value,
                source_id=source.id.value,
                payload=payload_of(commands[0]),
            )
        )

        read_back = repo.get_by_id_and_tenant(saved.id.value, tenant.id.value)
        assert read_back is not None
        assert read_back.payload["budget"] is None
        assert read_back.payload["first_name"] == "Juan"
    finally:
        ctx.__exit__(None, None, None)


def test_that_stored_record_is_then_rejected_by_the_domain(test_db):
    """Storing it is only half the fix: the phase that interprets it must
    reject it as a domain error, so the record lands as REJECTED with the
    budget field named, instead of crashing the run."""
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    try:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)
        commands = PandasFileParser().parse_leads_file(
            _CSV_WITH_A_BLANK_BUDGET, "leads.csv", tenant.id.value, source.id.value
        )
        record = RawSqlIntakeRecordRepository(conn).save(
            IntakeRecord.create(
                tenant_id=tenant.id.value,
                source_id=source.id.value,
                payload=payload_of(commands[0]),
            )
        )

        rebuilt = command_from_record(record)

        with pytest.raises(InvalidBudgetException) as exc_info:
            Lead.create(
                tenant_id=rebuilt.tenant_id,
                source_id=rebuilt.source_id,
                first_name=rebuilt.first_name,
                last_name=rebuilt.last_name,
                company=rebuilt.company,
                budget=rebuilt.budget,
                industry=rebuilt.industry,
            )

        assert exc_info.value.error_code == "INVALID_BUDGET"
    finally:
        ctx.__exit__(None, None, None)
