import json
from datetime import datetime, timezone
from uuid import uuid4

import pika
import pytest

from chassis.outbox import OutboxRow
from chassis.rabbit import RabbitJobDispatcher


def _row():
    return OutboxRow(id=uuid4(), channel="job", tenant_id="t-1", partition_key="job-1",
                     event_type="IntakeJobRequested", payload={"job_id": "job-1"},
                     occurred_on=datetime(2026, 1, 1, tzinfo=timezone.utc), correlation_id="corr")


class FakeChannel:
    def __init__(self, error=None):
        self.error, self.confirms, self.published, self.is_closed = error, 0, [], False

    def confirm_delivery(self): self.confirms += 1

    def basic_publish(self, **kwargs):
        if self.error:
            raise self.error
        self.published.append(kwargs)


class FakeConnection:
    def __init__(self, channel):
        self._channel, self.is_closed, self.closed = channel, False, False

    def channel(self): return self._channel

    def close(self):
        self.closed = True
        self.is_closed = True


class Factory:
    def __init__(self, *channels):
        self.connections = [FakeConnection(c) for c in channels]

    def __call__(self):
        return self.connections.pop(0)


def _dispatcher(factory, declared=None):
    declared = [] if declared is None else declared
    return RabbitJobDispatcher(
        "amqp://unused", "intake.jobs", declared.append,
        lambda row: {"message_id": str(row.id), "job_id": row.partition_key},
        connection_factory=factory,
    )


def test_publishes_persistent_mandatory_with_confirms_and_message_id():
    channel, row = FakeChannel(), _row()

    _dispatcher(Factory(channel)).dispatch(row)

    assert channel.confirms == 1
    (sent,) = channel.published
    assert (sent["exchange"], sent["routing_key"], sent["mandatory"]) == ("", "intake.jobs", True)
    assert json.loads(sent["body"]) == {"message_id": str(row.id), "job_id": "job-1"}
    assert sent["properties"].delivery_mode == 2
    assert sent["properties"].message_id == str(row.id)


def test_connection_is_lazy_reused_and_declared_once():
    channel, declared = FakeChannel(), []
    factory = Factory(channel)
    dispatcher = _dispatcher(factory, declared)
    assert len(factory.connections) == 1  # nothing opened by the constructor

    dispatcher.dispatch(_row())
    dispatcher.dispatch(_row())

    assert declared == [channel] and len(channel.published) == 2 and factory.connections == []


@pytest.mark.parametrize("error", [pika.exceptions.NackError([]), pika.exceptions.UnroutableError([])])
def test_a_nack_or_unroutable_message_raises_and_keeps_the_connection(error):
    channel = FakeChannel(error=error)
    factory = Factory(channel)
    dispatcher = _dispatcher(factory)

    with pytest.raises(RuntimeError):
        dispatcher.dispatch(_row())

    assert channel.published == [] and not channel.is_closed


def test_a_stale_reused_connection_is_replaced_and_the_publish_retried_once():
    stale, fresh, declared = FakeChannel(), FakeChannel(), []
    factory = Factory(stale, fresh)
    dispatcher = _dispatcher(factory, declared)
    dispatcher.dispatch(_row())
    stale.error = pika.exceptions.StreamLostError("idle socket died")

    dispatcher.dispatch(_row())

    assert len(stale.published) == 1 and len(fresh.published) == 1
    assert declared == [stale, fresh] and factory.connections == []


def test_a_nack_on_a_reused_connection_is_not_retried():
    channel, spare = FakeChannel(), FakeChannel()
    factory = Factory(channel, spare)
    dispatcher = _dispatcher(factory)
    dispatcher.dispatch(_row())
    channel.error = pika.exceptions.NackError([])

    with pytest.raises(RuntimeError):
        dispatcher.dispatch(_row())

    assert len(factory.connections) == 1 and spare.published == []


def test_a_retry_that_fails_too_raises_and_drops_the_connection():
    stale, also_bad = FakeChannel(), FakeChannel(error=ConnectionResetError("down"))
    dispatcher = _dispatcher(Factory(stale, also_bad, FakeChannel()))
    dispatcher.dispatch(_row())
    stale.error = pika.exceptions.StreamLostError("idle")

    with pytest.raises(ConnectionResetError):
        dispatcher.dispatch(_row())
    dispatcher.dispatch(_row())  # next call opens a third connection


def test_a_broken_connection_is_dropped_and_reopened_on_the_next_dispatch():
    broken, healthy, declared = FakeChannel(error=ConnectionResetError("gone")), FakeChannel(), []
    factory = Factory(broken, healthy)
    dispatcher = _dispatcher(factory, declared)

    with pytest.raises(ConnectionResetError):
        dispatcher.dispatch(_row())
    dispatcher.dispatch(_row())

    assert len(healthy.published) == 1 and declared == [broken, healthy]
