from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from application.use_cases.intake.payloads import command_from_record, payload_of
from domain.value_objects.tenant_id import TenantId
from domain.entities.intake_record import IntakeRecord
from domain.entities.lead import Lead
from domain.entities.lead_source import LeadSource
from domain.exceptions import InvalidBudgetException
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.raw_sql_intake_record_repository import (
    RawSqlIntakeRecordRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)

_CSV_WITH_A_BLANK_BUDGET = b"""first_name,last_name,email,company,budget,industry
Juan,Perez,jperez@smallbiz.es,SmallBiz Local,,Retail
"""


def _tenant(conn: psycopg.Connection) -> SimpleNamespace:
    # No row: since migration 017 nothing in leads_db references tenants.
    return SimpleNamespace(id=TenantId())


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
    with test_db.get_connection(autocommit=True) as conn:
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


def test_that_stored_record_is_then_rejected_by_the_domain(test_db):
    """Storing it is only half the fix: the persisted record must reconstruct
    via ``command_from_record`` and be rejected by the domain as a recoverable
    ``InvalidBudgetException``, instead of escaping as an exception no caller
    can translate. It does not exercise the non-finite guard in ``Money``
    itself -- the payload already round-tripped the blank cell to ``None``
    before this point; that guard is covered by the unit test
    ``test_money_rejects_non_finite_values``."""
    with test_db.get_connection(autocommit=True) as conn:
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


def test_a_payload_with_a_raw_nan_still_persists(test_db):
    """Reproduces the manual-intake path: ReceiveIntakeUseCase.execute() saves
    the payload exactly as it arrives from the HTTP endpoint, without routing
    it through ``payload_of``. The repository is the only point both the
    manual and the batch producers share, so that is where the guard has to
    live. Also covers the recursive case, since custom_attributes is a
    free-form dict fed by untrusted input."""
    with test_db.get_connection(autocommit=True) as conn:
        tenant = _tenant(conn)
        source = _source(conn, tenant.id.value)

        repo = RawSqlIntakeRecordRepository(conn)
        saved = repo.save(
            IntakeRecord.create(
                tenant_id=tenant.id.value,
                source_id=source.id.value,
                payload={
                    "budget": float("nan"),
                    "custom_attributes": {"nested": float("nan")},
                },
            )
        )

        read_back = repo.get_by_id_and_tenant(saved.id.value, tenant.id.value)
        assert read_back is not None
        assert read_back.payload["budget"] is None
        assert read_back.payload["custom_attributes"]["nested"] is None
