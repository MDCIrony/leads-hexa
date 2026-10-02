from uuid import uuid4

from infrastructure.adapters.output.persistence.raw_sql_processed_event_repository import (
    RawSqlProcessedEventRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlProcessedEventRepository(conn), ctx


def test_mark_is_true_once_and_false_on_redelivery(test_db):
    repo, ctx = _repo(test_db)
    try:
        event_id = uuid4()
        assert repo.mark("notifications.lead-events", event_id) is True
        assert repo.mark("notifications.lead-events", event_id) is False
    finally:
        ctx.__exit__(None, None, None)


def test_the_same_event_is_new_for_another_consumer(test_db):
    repo, ctx = _repo(test_db)
    try:
        event_id = uuid4()
        assert repo.mark("notifications.lead-events", event_id) is True
        assert repo.mark("notifications.intake-events", event_id) is True
    finally:
        ctx.__exit__(None, None, None)
