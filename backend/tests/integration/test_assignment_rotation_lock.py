"""What only two connections at once can prove.

The rest of the suite runs single-threaded, so the race this covers, reproduced
by hand against the real stack before being fixed, is invisible to it: every
assertion passes while the defect is present.
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

import pytest

from domain.entities.rule import AssignmentRule
from domain.entities.sales_group import SalesGroup
from domain.value_objects.enums import AssignmentStrategy
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
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


def test_the_rotation_cursor_is_read_under_a_lock(test_db, concurrent_db):
    """The cursor is read, advanced in Python and written back, so two
    admissions that read it at once both compute the same next advisor and the
    second write erases the first — the rotation stalls and consecutive leads
    land on the same person.

    Asserted as the lock itself rather than as a race between two admissions:
    that race is real but narrow, and a test that only fails sometimes proves
    nothing on the run where it passes."""
    tenant_id = uuid.uuid4()
    with test_db.get_connection(autocommit=True) as conn:
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
