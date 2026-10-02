import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from chassis.consumer import TopicSpec
from chassis.outbox import OutboxRelay, OutboxRow

from infrastructure.worker import build_dispatchers, ensure_topics_until_ready


def _row(channel: str) -> OutboxRow:
    return OutboxRow(
        id=uuid.uuid4(), channel=channel, tenant_id=None, partition_key="k",
        event_type="TenantState", payload={}, occurred_on=datetime.now(timezone.utc),
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


class _NoWaitEvent(threading.Event):
    """Skips the backoff sleep so the retry path runs instantly."""

    def wait(self, timeout=None):
        return self.is_set()


class _FlakyAdmin:
    def __init__(self, failures: int, topics: set[str]):
        self.failures, self.topics = failures, topics

    def list_topics(self, timeout):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("broker unavailable")
        return SimpleNamespace(topics={name: None for name in self.topics})


def test_the_job_channel_has_no_dispatcher_so_its_rows_stay_untouched():
    job = _row("job")
    store = _Store([job])
    relay = OutboxRelay(store.open, build_dispatchers([_Recorder()]))

    assert relay.drain("job") == 0

    assert store.published == [] and store.failed == []


def test_the_internal_channel_waits_for_its_dispatcher():
    internal = _row("internal")
    store = _Store([internal])
    dispatchers = build_dispatchers([_Recorder()])
    relay = OutboxRelay(store.open, dispatchers)

    assert relay.drain("internal") == 0
    assert store.failed == []

    internal_dispatcher = _Recorder()
    dispatchers["internal"].append(internal_dispatcher)

    assert relay.drain("internal") == 1
    assert internal_dispatcher.rows == [internal]


def test_topics_are_retried_until_kafka_answers_and_only_then_activated():
    specs = [TopicSpec("internal.a"), TopicSpec("internal.b")]
    admin = _FlakyAdmin(failures=2, topics={"internal.a", "internal.b"})
    activated = []

    ready = ensure_topics_until_ready(admin, specs, _NoWaitEvent(), lambda: activated.append(True))

    assert ready is True
    assert admin.failures == 0
    assert activated == [True]


def test_a_stop_during_the_retries_never_activates_the_channel():
    stop = _NoWaitEvent()
    admin = _FlakyAdmin(failures=100, topics=set())
    activated = []

    class _StopsAfterFirstFailure(_FlakyAdmin):
        def list_topics(self, timeout):
            stop.set()
            raise RuntimeError("broker unavailable")

    ready = ensure_topics_until_ready(
        _StopsAfterFirstFailure(0, set()), [TopicSpec("internal.a")], stop, lambda: activated.append(True),
    )

    assert ready is False
    assert activated == []
    assert admin.failures == 100
