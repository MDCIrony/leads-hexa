import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from chassis.consumer import TopicSpec
from chassis.outbox import OutboxRow

from infrastructure.worker.config import producer_config
from infrastructure.worker.lanes import ensure_topics_until_ready, run_consumer_lane
from infrastructure.worker.relays import build_dispatchers, build_relays


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


def test_a_channel_without_dispatchers_leaves_its_rows_untouched():
    job = _row("job")
    store = _Store([job])
    relay = build_relays(store.open, build_dispatchers([_Recorder()], []))["job"]

    assert relay.drain("job") == 0

    assert store.published == [] and store.failed == []


def test_the_internal_channel_waits_for_its_dispatcher():
    internal = _row("internal")
    store = _Store([internal])
    dispatchers = build_dispatchers([_Recorder()], [])
    relay = build_relays(store.open, dispatchers)["internal"]

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
    activated = []
    attempts = []

    class _StopsAfterFirstFailure(_FlakyAdmin):
        def list_topics(self, timeout):
            attempts.append(1)
            stop.set()
            raise RuntimeError("broker unavailable")

    ready = ensure_topics_until_ready(
        _StopsAfterFirstFailure(0, set()), [TopicSpec("internal.a")], stop, lambda: activated.append(True),
    )

    assert ready is False
    assert activated == []
    # Stopped on the first backoff, not retried until the broker answered.
    assert len(attempts) == 1


def test_each_channel_has_its_own_relay_that_drains_only_that_channel():
    product, internal = _row("product"), _row("internal")
    store = _Store([product, internal])
    product_dispatcher = _Recorder()
    dispatchers = build_dispatchers([product_dispatcher], [])
    relays = build_relays(store.open, dispatchers)

    assert set(relays) == {"product", "internal", "job"}
    assert relays["product"].drain_all() == {"product": 1}
    assert product_dispatcher.rows == [product]
    # `internal` is not active yet and its relay never touches `product`.
    assert relays["internal"].drain_all() == {"internal": 0}


def test_the_internal_producer_never_auto_creates_topics_and_the_timeout_is_below_the_flush():
    internal = producer_config("kafka:9092", auto_create_topics=False)
    product = producer_config("kafka:9092")

    assert internal["allow.auto.create.topics"] is False
    assert "allow.auto.create.topics" not in product
    # The dispatchers flush for 10 s.
    assert internal["message.timeout.ms"] < 10_000


class _Loop:
    def __init__(self, runs):
        self._runs = runs

    def run(self, stop):
        self._runs.append(1)


def test_a_consumer_lane_builds_a_new_consumer_after_each_failure_until_one_runs():
    ready, stop = threading.Event(), _NoWaitEvent()
    ready.set()
    runs, builds = [], []

    def build():
        builds.append(1)
        if len(builds) <= 2:
            raise RuntimeError("cannot subscribe")
        stop.set()
        return _Loop(runs)

    run_consumer_lane("g", build, ready, stop)

    assert len(builds) == 3
    assert runs == [1]


def test_a_consumer_lane_survives_a_loop_that_dies_while_running():
    ready, stop = threading.Event(), _NoWaitEvent()
    ready.set()
    builds = []

    class _FatalThenFine:
        def __init__(self, fail):
            self._fail = fail

        def run(self, stop):
            if self._fail:
                raise RuntimeError("fatal kafka error")
            stop.set()

    def build():
        builds.append(1)
        return _FatalThenFine(fail=len(builds) == 1)

    run_consumer_lane("g", build, ready, stop)

    assert len(builds) == 2


def test_a_stop_during_the_backoff_ends_the_lane_promptly():
    ready, stop = threading.Event(), threading.Event()
    ready.set()
    started = threading.Event()

    def build():
        started.set()
        raise RuntimeError("broker down")

    lane = threading.Thread(target=run_consumer_lane, args=("g", build, ready, stop))
    lane.start()
    assert started.wait(2)
    stop.set()
    lane.join(timeout=2)

    assert not lane.is_alive()


def test_a_stop_before_the_topics_are_ready_ends_the_lane_without_building():
    ready, stop = threading.Event(), threading.Event()
    stop.set()
    builds = []

    run_consumer_lane("g", lambda: builds.append(1), ready, stop)

    assert builds == []
