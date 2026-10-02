"""What only two connections at once can prove: the claim is the guard against two runs closing one record."""
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

import pytest
from chassis.persistence import RawSqlDatabase

from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
from tests.integration.persistence.helpers import seed_source


@pytest.fixture
def concurrent_db(test_db):
    """A pool of this module's own: borrowing several connections at once out of the
    suite-wide pool would grow it for every test that runs after."""
    database = RawSqlDatabase(test_db.dsn)
    yield database
    database.close()


def test_a_second_claim_waits_for_the_first_and_then_finds_the_record_closed(test_db, concurrent_db):
    with test_db.get_connection(autocommit=True) as conn:
        source = seed_source(conn)
    uow = PostgresUnitOfWork(concurrent_db)
    with uow:
        record = uow.intake_records.save(IntakeRecord.create(
            tenant_id=source.tenant_id.value, source_id=source.id.value, payload={}))
    tenant_id, record_id = source.tenant_id.value, record.id.value
    holding, release = threading.Event(), threading.Event()

    def first():
        with PostgresUnitOfWork(concurrent_db) as winner:
            claimed = winner.intake_records.claim_unpromoted(record_id, tenant_id)
            claimed.promote(source.id.value)
            winner.intake_records.save(claimed)
            holding.set()
            release.wait(timeout=10)
        return claimed is not None

    def second():
        with PostgresUnitOfWork(concurrent_db) as loser:
            return loser.intake_records.claim_unpromoted(record_id, tenant_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(first)
        assert holding.wait(timeout=10), "the first transaction never took the claim"
        contender = pool.submit(second)

        # Blocked while the first transaction holds the row; without FOR UPDATE it returns at once.
        with pytest.raises(FuturesTimeout):
            contender.result(timeout=1.5)

        release.set()
        assert winner.result(timeout=10) is True
        assert contender.result(timeout=10) is None

    stored = PostgresUnitOfWork(test_db)
    with stored:
        assert stored.intake_records.get_by_id_and_tenant(record_id, tenant_id).status == IntakeRecordStatus.PROMOTED
