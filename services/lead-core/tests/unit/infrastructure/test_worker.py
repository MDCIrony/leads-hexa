import threading
import types
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from chassis.outbox import OutboxRow

from infrastructure.worker import main as worker
from infrastructure.worker.relays import build_dispatchers, build_relays


def _row(channel: str) -> OutboxRow:
    return OutboxRow(
        id=uuid.uuid4(), channel=channel, tenant_id=None, partition_key="k",
        event_type="LeadAssigned", payload={}, occurred_on=datetime.now(timezone.utc),
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
    dispatchers = build_dispatchers([_Recorder()])
    relay = build_relays(store.open, dispatchers)["internal"]

    assert relay.drain("internal") == 0
    assert store.failed == []

    internal_dispatcher = _Recorder()
    dispatchers["internal"].append(internal_dispatcher)

    assert relay.drain("internal") == 1
    assert internal_dispatcher.rows == [internal]


def test_each_channel_has_its_own_relay_that_drains_only_that_channel():
    product, internal = _row("product"), _row("internal")
    store = _Store([product, internal])
    product_dispatcher = _Recorder()
    dispatchers = build_dispatchers([product_dispatcher])
    relays = build_relays(store.open, dispatchers)

    assert set(relays) == {"product", "internal"}
    assert relays["product"].drain_all() == {"product": 1}
    assert product_dispatcher.rows == [product]
    # `internal` is not active yet and its relay never touches `product`.
    assert relays["internal"].drain_all() == {"internal": 0}


def test_there_is_no_job_lane_any_more():
    # The queue and its dispatcher belong to intake now.
    assert "job" not in build_dispatchers([_Recorder()])


def test_the_internal_topic_of_intake_is_not_this_services_to_publish_on():
    from infrastructure.adapters.output.events.internal_topics import INTERNAL_TOPIC_SPECS, topic_for

    with pytest.raises(ValueError, match="IntakeRejected"):
        topic_for(OutboxRow(
            id=uuid.uuid4(), channel="internal", tenant_id=None, partition_key="k",
            event_type="IntakeRejected", payload={}, occurred_on=datetime.now(timezone.utc),
            correlation_id=None))
    assert [spec.name for spec in INTERNAL_TOPIC_SPECS] == ["internal.lead-core.events"]


class _Database:
    def __init__(self, dsn):
        self.dsn, self.closed = dsn, False

    def close(self):
        self.closed = True


class _Quiet:
    """Stands in for every Kafka client: no broker is reached."""

    def __init__(self, *args, **kwargs):
        pass


class _StoppedEvent(threading.Event):
    def wait(self, timeout=None):
        return True


def test_the_worker_starts_from_its_own_settings_and_builds_no_container(monkeypatch):
    """No JWKS and no service secret in the environment: the worker never verifies a bearer nor calls identity."""
    from infrastructure.di import container as container_module

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.test:9092")
    monkeypatch.delenv("JWKS_URL")
    monkeypatch.delenv("SERVICE_CLIENT_SECRET")

    def refuse(*args, **kwargs):
        raise AssertionError("the worker must not build the API container")

    databases = []
    monkeypatch.setattr(container_module, "Container", refuse)
    monkeypatch.setattr(worker, "RawSqlDatabase", lambda dsn: databases.append(_Database(dsn)) or databases[-1])
    for name in ("Producer", "AdminClient"):
        monkeypatch.setattr(worker, name, _Quiet)
    for name in ("run_relay", "ensure_topics_until_ready", "run_consumer_lane"):
        monkeypatch.setattr(worker, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "signal", types.SimpleNamespace(
        signal=lambda *args: None, SIGTERM=15, SIGINT=2))
    monkeypatch.setattr(worker, "threading", types.SimpleNamespace(Event=_StoppedEvent, Thread=threading.Thread))

    assert worker.main() == 0
    assert not hasattr(worker, "Container")
    assert [(db.dsn, db.closed) for db in databases] == [("postgresql://u:p@host:5432/db", True)]
