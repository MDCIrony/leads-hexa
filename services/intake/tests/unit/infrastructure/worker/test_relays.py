import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from chassis.outbox import OutboxRow

from infrastructure.worker.relays import build_dispatchers, build_relays


def _row(channel: str) -> OutboxRow:
    return OutboxRow(
        id=uuid.uuid4(), channel=channel, tenant_id=None, partition_key="k",
        event_type="IntakeRejected", payload={}, occurred_on=datetime.now(timezone.utc),
        correlation_id=None,
    )


class _Store:
    def __init__(self, rows):
        self.rows = rows
        self.published, self.failed = [], []

    def fetch(self, channel, limit):
        return [row for row in self.rows if row.channel == channel]

    def mark_published(self, row_id):
        self.published.append(row_id)

    def mark_failed(self, row_id, error):
        self.failed.append(row_id)

    @contextmanager
    def open(self):
        yield self


class _Recorder:
    def __init__(self):
        self.rows = []

    def dispatch(self, row):
        self.rows.append(row)


def test_the_internal_channel_waits_for_its_dispatcher():
    internal = _row("internal")
    store = _Store([internal])
    dispatchers = build_dispatchers(_Recorder())
    relay = build_relays(store.open, dispatchers)["internal"]

    assert relay.drain("internal") == 0
    assert store.failed == []

    internal_dispatcher = _Recorder()
    dispatchers["internal"].append(internal_dispatcher)

    assert relay.drain("internal") == 1
    assert internal_dispatcher.rows == [internal]


def test_each_channel_has_its_own_relay_that_drains_only_that_channel():
    job, internal = _row("job"), _row("internal")
    store = _Store([job, internal])
    job_dispatcher = _Recorder()
    relays = build_relays(store.open, build_dispatchers(job_dispatcher))

    assert set(relays) == {"internal", "job"}
    assert relays["job"].drain_all() == {"job": 1}
    assert job_dispatcher.rows == [job]
    # `internal` is not active yet, and its relay never touches `job`.
    assert relays["internal"].drain_all() == {"internal": 0}
    assert store.published == [job.id]
