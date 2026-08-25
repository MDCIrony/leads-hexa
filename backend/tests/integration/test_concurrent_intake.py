"""What only two connections at once can prove.

The rest of the suite runs single-threaded, so the two races these cover —
both reproduced by hand against the real stack before being fixed — are
invisible to it: every assertion passes while the defect is present.
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

import pytest

from application.dtos.commands import IngestLeadCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase, payload_of
from domain.entities.intake_record import IntakeRecord
from domain.entities.lead_source import LeadSource
from domain.entities.rule import AssignmentRule
from domain.entities.sales_group import SalesGroup
from domain.value_objects.enums import AssignmentStrategy, LeadSourceKind
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.persistence.raw_sql_intake_record_repository import (
    RawSqlIntakeRecordRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import RawSqlRuleRepository
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import (
    RawSqlSalesGroupRepository,
)



@pytest.fixture
def concurrent_db(dsn_of_test_db):
    """A pool of this module's own.

    Borrowing several connections at once out of the suite-wide pool grows it,
    and the next test to assert that two sequential borrows reuse one backend
    process then fails depending on what ran before it."""
    database = RawSqlDatabase(dsn=dsn_of_test_db)
    yield database
    database.close()


def _seed_tenant(conn, tenant_id: uuid.UUID) -> uuid.UUID:
    conn.execute(
        "INSERT INTO tenants (id, name, slug, created_at) VALUES (%s, %s, %s, now())",
        (tenant_id, "Concurrencia", f"conc-{tenant_id}"),
    )
    source = RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant_id, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
    )
    return source.id.value


def _command(tenant_id, source_id, name="Ana") -> IngestLeadCommand:
    return IngestLeadCommand(
        tenant_id=tenant_id,
        source_id=source_id,
        first_name=name,
        last_name="Diaz",
        email=f"{name.lower()}-{uuid.uuid4().hex[:6]}@x.test",
        phone=None,
        company="Acme",
        budget=1000.0,
        industry="tech",
        custom_attributes={},
    )


def test_two_runs_over_the_same_record_produce_one_lead(test_db, concurrent_db):
    """A manual reprocess landing on a job the worker is already draining used
    to have both runs read the same PENDING record and each build its own Lead
    from it: the same person twice, under two ids, published twice on the
    outbound channel where no event_id can reconcile them."""
    tenant_id = uuid.uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        source_id = _seed_tenant(conn, tenant_id)
        command = _command(tenant_id, source_id)
        record = RawSqlIntakeRecordRepository(conn).save(
            IntakeRecord.create(
                tenant_id=tenant_id, source_id=source_id, payload=payload_of(command)
            )
        )

    def run():
        # One unit of work per thread: it holds a connection, and sharing it
        # would serialise the very thing this test needs to happen at once.
        return IngestLeadUseCase(uow=PostgresUnitOfWork(concurrent_db)).execute(
            command, existing_record=record
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in [pool.submit(run), pool.submit(run)]]

    with test_db.get_connection(autocommit=True) as conn:
        leads = conn.execute(
            "SELECT COUNT(*) AS n FROM leads WHERE tenant_id = %s", (tenant_id,)
        ).fetchone()["n"]
        events = conn.execute(
            "SELECT COUNT(*) AS n FROM outbox_events WHERE tenant_id = %s", (str(tenant_id),)
        ).fetchone()["n"]

    assert leads == 1
    assert events == 1
    # Both callers get the same answer: the loser reports the winner's lead
    # rather than an error, so a redelivered message stays idempotent.
    assert results[0].lead_id == results[1].lead_id


def test_the_rotation_cursor_is_read_under_a_lock(test_db, concurrent_db):
    """The cursor is read, advanced in Python and written back, so two
    ingestions that read it at once both compute the same next advisor and the
    second write erases the first — the rotation stalls and consecutive leads
    land on the same person.

    Asserted as the lock itself rather than as a race between two ingestions:
    that race is real but narrow, and a test that only fails sometimes proves
    nothing on the run where it passes."""
    tenant_id = uuid.uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        _seed_tenant(conn, tenant_id)
        group = RawSqlSalesGroupRepository(conn).save(
            SalesGroup.create(
                tenant_id=tenant_id, name="Equipo",
                default_strategy=AssignmentStrategy.ROUND_ROBIN,
            )
        )
        RawSqlRuleRepository(conn).save_assignment_rule(tenant_id, AssignmentRule.create(
            tenant_id=tenant_id,
            name="Todo al equipo",
            min_score=0,
            target_group_id=group.id.value,
            strategy=AssignmentStrategy.ROUND_ROBIN,
        ))

    holding = threading.Event()
    release = threading.Event()

    def hold_the_lock():
        uow = PostgresUnitOfWork(concurrent_db)
        with uow:
            uow.rules.lock_assignment_rules_by_tenant(tenant_id)
            holding.set()
            release.wait(timeout=10)

    def try_to_take_it():
        uow = PostgresUnitOfWork(concurrent_db)
        with uow:
            uow.rules.lock_assignment_rules_by_tenant(tenant_id)
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(hold_the_lock)
        assert holding.wait(timeout=10), "the first transaction never took the lock"
        contender = pool.submit(try_to_take_it)

        # Still blocked while the first transaction holds the rows. Without
        # FOR UPDATE this returns immediately and the assertion fails.
        with pytest.raises(FuturesTimeout):
            contender.result(timeout=1.5)

        release.set()
        assert contender.result(timeout=10) is True
        holder.result(timeout=10)
