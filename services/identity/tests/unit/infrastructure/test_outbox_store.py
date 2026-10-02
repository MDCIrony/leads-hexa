import uuid
from datetime import datetime, timezone

from infrastructure.adapters.output.persistence.outbox_store import PostgresOutboxStore


class _Connection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query, params):
        return self

    def fetchall(self):
        return self._rows


def test_a_naive_timestamp_is_read_as_utc():
    naive = datetime(2026, 1, 1, 12, 0)
    row = {
        "id": uuid.uuid4(), "tenant_id": None, "partition_key": "k", "event_type": "AgentState",
        "payload": {}, "occurred_on": naive, "channel": "internal", "correlation_id": None,
    }

    [fetched] = PostgresOutboxStore(_Connection([row])).fetch("internal", 10)

    # Without an offset the envelope would be read as local time by its consumers.
    assert fetched.occurred_on == naive.replace(tzinfo=timezone.utc)
    assert fetched.occurred_on.isoformat().endswith("+00:00")
