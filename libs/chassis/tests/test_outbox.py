import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from chassis.outbox import KafkaEventDispatcher, OutboxRelay, OutboxRow, envelope, run_relay
from chassis.web import request_id_var


def _row(channel="internal", correlation_id="corr-1", tenant_id="t-1", **overrides):
    values = dict(
        id=uuid4(), channel=channel, tenant_id=tenant_id, partition_key="lead-9",
        event_type="LeadAssigned", payload={"lead_id": "lead-9"},
        occurred_on=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        correlation_id=correlation_id,
    )
    values.update(overrides)
    return OutboxRow(**values)


class FakeStore:
    """Records every call, in order, in a log shared with the dispatchers."""

    def __init__(self, rows, log, broken=()):
        self.rows, self.log, self.broken = rows, log, set(broken)

    @contextmanager
    def open(self):
        self.log.append("open")
        try:
            yield self
        finally:
            self.log.append("close")

    def fetch(self, channel, limit):
        self.log.append(f"fetch:{channel}:{limit}")
        if channel in self.broken:
            raise ConnectionError(f"{channel} store down")
        return list(self.rows.get(channel, []))

    def mark_published(self, row_id):
        self.log.append(f"published:{row_id}")

    def mark_failed(self, row_id, error):
        self.log.append(f"failed:{row_id}:{error}")


class FakeDispatcher:
    def __init__(self, name, log, fail=False):
        self.name, self.log, self.fail = name, log, fail
        self.seen_request_ids = []

    def dispatch(self, row):
        self.log.append(f"dispatch:{self.name}:{row.id}")
        self.seen_request_ids.append(request_id_var.get())
        if self.fail:
            raise RuntimeError(f"{self.name} down")


def test_drain_reads_then_delivers_outside_the_transaction_then_records():
    log = []
    rows = [_row(), _row()]
    relay = OutboxRelay(FakeStore({"internal": rows}, log).open,
                        {"internal": [FakeDispatcher("kafka", log)]})

    assert relay.drain("internal", batch_size=50) == 2

    assert log == [
        "open", "fetch:internal:50", "close",
        f"dispatch:kafka:{rows[0].id}", f"dispatch:kafka:{rows[1].id}",
        "open", f"published:{rows[0].id}", f"published:{rows[1].id}", "close",
    ]


def test_a_failing_channel_does_not_affect_the_others(caplog):
    log = []
    product, internal = [_row("product")], [_row("internal"), _row("internal")]
    relay = OutboxRelay(
        FakeStore({"product": product, "internal": internal}, log).open,
        {"product": [FakeDispatcher("webhook", log, fail=True)],
         "internal": [FakeDispatcher("kafka", log)]},
    )

    with caplog.at_level(logging.CRITICAL):
        assert relay.drain_all() == {"product": 0, "internal": 2}

    assert f"failed:{product[0].id}:webhook down" in log
    assert all(f"published:{r.id}" in log for r in internal)


def test_a_channel_that_cannot_be_read_does_not_starve_the_others(caplog):
    log = []
    relay = OutboxRelay(
        FakeStore({"internal": [_row("internal")]}, log, broken={"product"}).open,
        {"product": [FakeDispatcher("webhook", log)], "internal": [FakeDispatcher("kafka", log)]},
    )

    with caplog.at_level(logging.CRITICAL):
        assert relay.drain_all() == {"product": 0, "internal": 1}


def test_a_failing_dispatcher_does_not_stop_the_others_of_its_channel(caplog):
    log = []
    row = _row("product")
    relay = OutboxRelay(
        FakeStore({"product": [row]}, log).open,
        {"product": [FakeDispatcher("a", log, fail=True), FakeDispatcher("b", log)]},
    )

    with caplog.at_level(logging.CRITICAL):
        assert relay.drain("product") == 0

    assert f"dispatch:b:{row.id}" in log
    assert f"failed:{row.id}:a down" in log
    assert f"published:{row.id}" not in log


def test_a_channel_without_dispatchers_is_not_drained():
    log = []
    relay = OutboxRelay(FakeStore({"job": [_row("job")]}, log).open, {"job": [], "internal": []})

    assert relay.drain("job") == 0
    assert relay.drain("never-heard-of") == 0
    assert relay.drain_all() == {"job": 0, "internal": 0}
    assert log == []


def test_dispatch_runs_with_the_row_correlation_id_and_restores_it():
    log = []
    dispatcher = FakeDispatcher("kafka", log)
    relay = OutboxRelay(FakeStore({"internal": [_row(correlation_id="abc")]}, log).open,
                        {"internal": [dispatcher]})

    relay.drain("internal")

    assert dispatcher.seen_request_ids == ["abc"]
    assert request_id_var.get() == "-"


def test_run_relay_survives_a_failed_pass(caplog):
    stop = threading.Event()

    class Flaky:
        passes = 0

        def drain_all(self, batch_size=100):
            self.passes += 1
            if self.passes == 1:
                raise ConnectionError("database away")
            if self.passes == 3:
                stop.set()
            return {}

    relay = Flaky()
    with caplog.at_level(logging.CRITICAL):
        run_relay(relay, stop, interval_seconds=0)

    assert relay.passes == 3


def test_envelope_has_the_exact_shape():
    row = _row()

    assert envelope(row, "lead-core") == {
        "event_id": str(row.id), "event_type": "LeadAssigned", "schema_version": 1,
        "occurred_at": "2026-01-02T03:04:05+00:00", "producer": "lead-core",
        "tenant_id": "t-1", "aggregate_id": "lead-9", "correlation_id": "corr-1",
        "payload": {"lead_id": "lead-9"},
    }

    bare = envelope(_row(tenant_id=None, correlation_id=None), "p", schema_version=2)
    assert (bare["tenant_id"], bare["correlation_id"], bare["schema_version"]) == (None, None, 2)


class FakeProducer:
    def __init__(self, delivery_error=None, pending=0):
        self.delivery_error, self.pending = delivery_error, pending
        self.produced = []

    def produce(self, **kwargs):
        self.produced.append(kwargs)
        kwargs["on_delivery"](self.delivery_error, None)

    def flush(self, timeout):
        return self.pending


def _dispatcher(producer):
    return KafkaEventDispatcher(producer, "lead-core", lambda row: "internal.lead-core.events")


def test_kafka_dispatcher_publishes_the_envelope_with_key_and_headers():
    producer, row = FakeProducer(), _row()

    _dispatcher(producer).dispatch(row)

    (sent,) = producer.produced
    assert sent["topic"] == "internal.lead-core.events"
    assert sent["key"] == b"lead-9"
    assert json.loads(sent["value"]) == envelope(row, "lead-core")
    assert sent["headers"] == [("event_type", b"LeadAssigned"), ("correlation_id", b"corr-1")]


def test_kafka_dispatcher_omits_an_absent_correlation_id_header():
    producer = FakeProducer()

    _dispatcher(producer).dispatch(_row(correlation_id=None))

    assert producer.produced[0]["headers"] == [("event_type", b"LeadAssigned")]


def test_kafka_dispatcher_raises_on_a_failed_delivery_callback():
    with pytest.raises(RuntimeError, match="delivery failed"):
        _dispatcher(FakeProducer(delivery_error="broker said no")).dispatch(_row())


def test_kafka_dispatcher_raises_when_flush_leaves_messages_pending():
    with pytest.raises(RuntimeError, match="timed out"):
        _dispatcher(FakeProducer(pending=1)).dispatch(_row())


def test_an_outage_logs_one_traceback_per_pass_not_one_per_row(caplog):
    log = []
    rows = [_row("job"), _row("job"), _row("job")]
    relay = OutboxRelay(FakeStore({"job": rows}, log).open, {"job": [FakeDispatcher("rabbit", log, fail=True)]})

    with caplog.at_level(logging.WARNING, logger="chassis.outbox"):
        assert relay.drain("job") == 0

    failures = [r for r in caplog.records if "failed for outbox row" in r.getMessage()]
    assert len(failures) == 3
    assert [bool(r.exc_info) for r in failures] == [True, False, False]
    assert all("rabbit down" in r.getMessage() for r in failures[1:])
