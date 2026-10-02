from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.records.intake_record import IntakeRecord
from infrastructure.adapters.output.persistence.intake_record_repository import PostgresIntakeRecordRepository
from infrastructure.cli.promoted_records import promoted_since
from tests.integration.persistence.helpers import seed_source


def _promoted(conn, source, processed_at):
    record = IntakeRecord.create(tenant_id=source.tenant_id.value, source_id=source.id.value, payload={})
    record.promote(str(uuid4()))
    record.processed_at = processed_at
    return PostgresIntakeRecordRepository(conn).save(record)


def test_walks_only_promoted_records_since_the_cutoff_in_pages(test_db):
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    with test_db.get_connection(autocommit=True) as conn:
        source = seed_source(conn)
        old = _promoted(conn, source, since - timedelta(minutes=1))
        # Two closed at the same instant: the id breaks the tie, so paging neither skips nor repeats.
        recent = [_promoted(conn, source, since + timedelta(minutes=m)) for m in (0, 1, 1, 2, 3)]
        pending = IntakeRecord.create(tenant_id=source.tenant_id.value, source_id=source.id.value, payload={})
        PostgresIntakeRecordRepository(conn).save(pending)

    pages = list(promoted_since(test_db, since, batch_size=2))

    assert [len(page) for page in pages] == [2, 2, 1]
    walked = [r.record_id for page in pages for r in page]
    assert sorted(walked) == sorted(r.id.value for r in recent)
    assert old.id.value not in walked and pending.id.value not in walked
    first = pages[0][0]
    assert (first.tenant_id, first.lead_id) == (source.tenant_id.value, recent[0].lead_id.value)
