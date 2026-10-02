import json
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from chassis.outbox import OutboxRow

from infrastructure.config.settings import WorkerSettings
from infrastructure.worker import main as worker


def _row(event_type: str, channel: str = "internal") -> OutboxRow:
    return OutboxRow(
        id=uuid.uuid4(), channel=channel, tenant_id=None, partition_key="k", event_type=event_type,
        payload={"x": 1}, occurred_on=datetime.now(timezone.utc), correlation_id=None,
    )


class _Store:
    def __init__(self, rows):
        self.rows, self.published, self.failed = rows, [], []

    def fetch(self, channel, limit):
        return [row for row in self.rows if row.channel == channel]

    def mark_published(self, row_id):
        self.published.append(row_id)

    def mark_failed(self, row_id, error):
        self.failed.append(row_id)


class _Producer:
    def __init__(self, config):
        self.config = config
        self.produced = []

    def produce(self, **kwargs):
        self.produced.append(kwargs)
        kwargs["on_delivery"](None, None)

    def flush(self, timeout):
        return 0


class _Database:
    def __init__(self, dsn):
        self.dsn, self.closed = dsn, False

    def close(self):
        self.closed = True


@pytest.fixture
def wired(monkeypatch):
    """Runs the worker with no broker and no database, capturing what it wires."""
    captured = {"relays": [], "topics": [], "databases": []}
    store = _Store([_row("AgentState"), _row("TenantState"), _row("LeadAssigned", channel="product")])
    producers = []

    def make_producer(config):
        producers.append(_Producer(config))
        return producers[-1]

    def make_database(dsn):
        captured["databases"].append(_Database(dsn))
        return captured["databases"][-1]

    monkeypatch.setattr(worker, "Producer", make_producer)
    monkeypatch.setattr(worker, "AdminClient", lambda config: config)
    monkeypatch.setattr(worker, "RawSqlDatabase", make_database)
    monkeypatch.setattr(
        worker, "open_outbox_store", contextmanager(lambda database: (yield store)),
    )
    monkeypatch.setattr(worker, "run_relay", lambda relay, stop, interval: captured["relays"].append((relay, interval)))
    monkeypatch.setattr(
        worker, "ensure_topics_until_ready",
        lambda admin, specs, stop, on_ready: captured["topics"].append((admin, specs, on_ready)),
    )
    stop = threading.Event()
    stop.set()
    worker.run(WorkerSettings("postgresql://x", "kafka:9092", outbox_relay_interval_seconds=0.5), stop)
    return captured, store, producers


def test_the_worker_relays_only_the_internal_channel_and_waits_for_its_topics(wired):
    captured, store, producers = wired
    [(relay, interval)] = captured["relays"]

    assert interval == 0.5
    # Rows wait, untouched, until the topics exist.
    assert relay.drain_all() == {"internal": 0}
    assert store.published == [] and store.failed == []

    [(admin, specs, on_ready)] = captured["topics"]
    assert admin == {"bootstrap.servers": "kafka:9092"}
    assert [spec.name for spec in specs] == ["internal.identity.agents", "internal.identity.tenants"]
    on_ready()

    assert relay.drain_all() == {"internal": 2}
    assert len(store.published) == 2 and store.failed == []
    [producer] = producers
    assert [(call["topic"], json.loads(call["value"])["producer"]) for call in producer.produced] == [
        ("internal.identity.agents", "identity"), ("internal.identity.tenants", "identity"),
    ]


def test_the_producer_never_auto_creates_topics(wired):
    _, _, producers = wired

    assert producers[0].config["allow.auto.create.topics"] is False
    assert producers[0].config["bootstrap.servers"] == "kafka:9092"


def test_the_database_is_closed_on_shutdown(wired):
    captured, _, _ = wired

    assert [(db.dsn, db.closed) for db in captured["databases"]] == [("postgresql://x", True)]
