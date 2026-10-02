import json
import logging
import threading
from uuid import uuid4

import pytest
from confluent_kafka import KafkaError, KafkaException

from chassis.consumer import ConsumerLoop, Envelope, TopicSpec, dlq_topic, ensure_topics
from chassis.web import request_id_var

GROUP = "notifications.lead-events"


def _body(**overrides):
    values = {"event_id": str(uuid4()), "event_type": "LeadAssigned", "schema_version": 1,
              "occurred_at": "2026-01-02T03:04:05+00:00", "producer": "lead-core",
              "tenant_id": "t-1", "aggregate_id": "lead-9", "correlation_id": "corr-1",
              "payload": {"lead_id": "lead-9"}}
    values.update(overrides)
    return values


def _raw(**overrides):
    return json.dumps(_body(**overrides)).encode()


class FakeMessage:
    def __init__(self, value, key=b"lead-9", topic="internal.lead-core.events",
                 partition=2, offset=41, error=None,
                 headers=(("event_type", b"LeadAssigned"), ("correlation_id", b"corr-1"))):
        self._value, self._key, self._topic = value, key, topic
        self._partition, self._offset = partition, offset
        self._error, self._headers = error, list(headers)

    def value(self): return self._value
    def key(self): return self._key
    def topic(self): return self._topic
    def partition(self): return self._partition
    def offset(self): return self._offset
    def error(self): return self._error
    def headers(self): return self._headers


class FakeConsumer:
    def __init__(self, messages=(), stop=None):
        self.queue, self.stop = list(messages), stop
        self.commits, self.seeks, self.subscribed, self.closed = [], [], None, False

    def subscribe(self, topics): self.subscribed = topics
    def commit(self, **kwargs): self.commits.append(kwargs)
    def seek(self, partition): self.seeks.append(partition)
    def close(self): self.closed = True

    def poll(self, timeout):
        if self.queue:
            return self.queue.pop(0)
        self.stop.set()
        return None


class FakeProducer:
    def __init__(self, delivery_error=None, pending=0):
        self.delivery_error, self.pending, self.produced = delivery_error, pending, []

    def produce(self, **kwargs):
        self.produced.append(kwargs)
        kwargs["on_delivery"](self.delivery_error, None)

    def flush(self, timeout): return self.pending


def _loop(handle, consumer=None, producer=None, sleeps=None):
    sleeps = [] if sleeps is None else sleeps
    return ConsumerLoop(consumer or FakeConsumer(), producer or FakeProducer(), GROUP,
                        ["internal.lead-core.events"], handle, sleep=sleeps.append,
                        rewind_delay_seconds=0)


# Envelope

def test_envelope_from_bytes_parses_a_valid_message():
    body = _body()

    parsed = Envelope.from_bytes(json.dumps(body).encode())

    assert str(parsed.event_id) == body["event_id"]
    assert (parsed.event_type, parsed.schema_version, parsed.producer) == ("LeadAssigned", 1, "lead-core")
    assert (parsed.tenant_id, parsed.aggregate_id, parsed.correlation_id) == ("t-1", "lead-9", "corr-1")
    assert parsed.payload == {"lead_id": "lead-9"}


def test_envelope_accepts_null_tenant_and_correlation():
    parsed = Envelope.from_bytes(_raw(tenant_id=None, correlation_id=None))

    assert parsed.tenant_id is None and parsed.correlation_id is None


@pytest.mark.parametrize("raw", [
    b"\xff\xfe not utf8", b"not json", b"[]", b"null",
    json.dumps({k: v for k, v in _body().items() if k != "event_type"}).encode(),
    _raw(event_id="not-a-uuid"),
    _raw(schema_version="1"),
    _raw(payload=[1]),
    _raw(event_type=3),
])
def test_envelope_rejects_anything_malformed(raw):
    with pytest.raises(ValueError):
        Envelope.from_bytes(raw)


# ConsumerLoop.process

def test_a_handled_message_commits_synchronously():
    consumer, handled = FakeConsumer(), []
    message = FakeMessage(_raw())

    assert _loop(handled.append, consumer).process(message) == "handled"

    assert len(handled) == 1
    assert consumer.commits == [{"message": message, "asynchronous": False}]


def test_a_handler_that_recovers_commits_once_and_never_dead_letters():
    consumer, producer, sleeps, calls = FakeConsumer(), FakeProducer(), [], []

    def flaky(envelope):
        calls.append(envelope)
        if len(calls) < 3:
            raise RuntimeError("transient")

    assert _loop(flaky, consumer, producer, sleeps).process(FakeMessage(_raw())) == "handled"

    assert len(calls) == 3 and sleeps == [0.2, 0.5]
    assert len(consumer.commits) == 1 and producer.produced == []


def test_exhausted_attempts_dead_letter_the_original_message_and_commit():
    consumer, producer, sleeps, calls = FakeConsumer(), FakeProducer(), [], []
    raw, message = _raw(), None
    message = FakeMessage(raw)

    def broken(envelope):
        calls.append(envelope)
        raise RuntimeError("boom")

    assert _loop(broken, consumer, producer, sleeps).process(message) == "dead-lettered"

    assert len(calls) == 3
    (sent,) = producer.produced
    assert sent["topic"] == "internal.dlq." + GROUP == dlq_topic(GROUP)
    assert (sent["value"], sent["key"]) == (raw, b"lead-9")
    assert dict(sent["headers"]) == {
        "event_type": b"LeadAssigned", "correlation_id": b"corr-1",
        "error": b"boom", "original_topic": b"internal.lead-core.events",
        "original_partition": b"2", "original_offset": b"41", "attempts": b"3",
    }
    assert consumer.commits == [{"message": message, "asynchronous": False}]


def test_garbage_goes_straight_to_the_dlq_without_calling_handle():
    consumer, producer, calls = FakeConsumer(), FakeProducer(), []

    assert _loop(calls.append, consumer, producer).process(FakeMessage(b"garbage")) == "dead-lettered"

    assert calls == []
    assert producer.produced[0]["value"] == b"garbage"
    assert dict(producer.produced[0]["headers"])["attempts"] == b"0"
    assert len(consumer.commits) == 1


def test_deeply_nested_garbage_is_dead_lettered_not_fatal():
    consumer, producer, calls = FakeConsumer(), FakeProducer(), []
    message = FakeMessage(b"[" * 100000)

    assert _loop(calls.append, consumer, producer).process(message) == "dead-lettered"

    assert calls == []
    assert consumer.commits == [{"message": message, "asynchronous": False}]


def test_garbage_without_original_headers_still_dead_letters():
    producer = FakeProducer()

    _loop(lambda e: None, producer=producer).process(FakeMessage(b"garbage", headers=()))

    assert [k for k, _ in producer.produced[0]["headers"]][0] == "error"


@pytest.mark.parametrize("producer", [FakeProducer(delivery_error="no"), FakeProducer(pending=1)])
def test_a_failing_dlq_leaves_the_offset_uncommitted_and_raises(producer):
    consumer = FakeConsumer()

    def broken(envelope):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _loop(broken, consumer, producer).process(FakeMessage(_raw()))

    assert consumer.commits == []


def test_handle_sees_the_envelope_correlation_id_and_it_is_restored():
    seen = []

    _loop(lambda envelope: seen.append(request_id_var.get())).process(FakeMessage(_raw(correlation_id="abc")))

    assert seen == ["abc"]
    assert request_id_var.get() == "-"


# ConsumerLoop.run

def test_run_subscribes_processes_until_stopped_and_closes():
    stop, handled = threading.Event(), []
    consumer = FakeConsumer([FakeMessage(_raw()), FakeMessage(_raw())], stop)

    _loop(handled.append, consumer).run(stop, poll_timeout=0)

    assert consumer.subscribed == ["internal.lead-core.events"]
    assert len(handled) == 2 and len(consumer.commits) == 2 and consumer.closed


def test_run_rewinds_to_the_failed_message_when_the_dlq_is_down(caplog):
    stop = threading.Event()
    consumer = FakeConsumer([FakeMessage(_raw(), partition=1, offset=7)], stop)

    def broken(envelope):
        raise RuntimeError("boom")

    loop = ConsumerLoop(consumer, FakeProducer(pending=1), GROUP, ["t"], broken,
                        sleep=lambda seconds: None, rewind_delay_seconds=0)
    with caplog.at_level(logging.CRITICAL):
        loop.run(stop, poll_timeout=0)

    assert consumer.commits == []
    (partition,) = consumer.seeks
    assert (partition.topic, partition.partition, partition.offset) == ("internal.lead-core.events", 1, 7)
    assert consumer.closed


def test_run_skips_messages_carrying_an_error_without_committing(caplog):
    stop, handled = threading.Event(), []
    eof = FakeMessage(None, error=KafkaError(KafkaError._PARTITION_EOF))
    broken = FakeMessage(None, error=KafkaError(KafkaError._TRANSPORT))
    consumer = FakeConsumer([eof, broken, FakeMessage(_raw())], stop)

    with caplog.at_level(logging.DEBUG, logger="chassis.consumer"):
        _loop(handled.append, consumer).run(stop, poll_timeout=0)

    assert len(handled) == 1 and len(consumer.commits) == 1
    levels = {r.levelno for r in caplog.records}
    assert levels == {logging.DEBUG, logging.WARNING}


def test_run_keeps_polling_when_the_rewind_itself_fails(caplog):
    stop, handled = threading.Event(), []
    consumer = FakeConsumer([FakeMessage(_raw()), FakeMessage(_raw())], stop)
    consumer.seek = lambda partition: (_ for _ in ()).throw(KafkaException(KafkaError(KafkaError._STATE)))
    attempts = []

    def flaky(envelope):
        attempts.append(envelope)
        raise RuntimeError("boom")

    loop = ConsumerLoop(consumer, FakeProducer(pending=1), GROUP, ["t"], flaky,
                        max_attempts=1, rewind_delay_seconds=0)
    with caplog.at_level(logging.CRITICAL):
        loop.run(stop, poll_timeout=0)

    assert len(attempts) == 2 and consumer.closed


def test_run_waits_the_dedicated_delay_after_a_rewind():
    waits = []

    class RecordingStop(threading.Event):
        def wait(self, timeout=None):
            waits.append(timeout)
            return super().wait(0)

    stop = RecordingStop()
    consumer = FakeConsumer([FakeMessage(_raw())], stop)
    loop = ConsumerLoop(consumer, FakeProducer(pending=1), GROUP, ["t"], lambda e: 1 / 0,
                        max_attempts=1, sleep=lambda s: None, rewind_delay_seconds=2.5)

    loop.run(stop, poll_timeout=0.1)

    assert waits == [2.5]


# ensure_topics

class FakeFuture:
    def __init__(self, error=None): self.error = error
    def result(self, timeout=None):
        if self.error:
            raise KafkaException(KafkaError(self.error))


class FakeAdmin:
    def __init__(self, existing=(), errors=None):
        self.existing, self.errors, self.created = set(existing), errors or {}, []

    def list_topics(self, timeout=None):
        return type("Metadata", (), {"topics": {name: object() for name in self.existing}})()

    def create_topics(self, new_topics, request_timeout=None):
        self.created.extend(new_topics)
        return {t.topic: FakeFuture(self.errors.get(t.topic)) for t in new_topics}


def test_ensure_topics_creates_only_what_is_missing():
    admin = FakeAdmin(existing={"a"})

    ensure_topics(admin, [TopicSpec("a"), TopicSpec("b", partitions=1, config={"cleanup.policy": "compact"})])

    (created,) = admin.created
    assert (created.topic, created.num_partitions, created.config) == ("b", 1, {"cleanup.policy": "compact"})


def test_ensure_topics_ignores_a_topic_created_in_the_meantime():
    admin = FakeAdmin(errors={"a": KafkaError.TOPIC_ALREADY_EXISTS})

    ensure_topics(admin, [TopicSpec("a")])

    assert len(admin.created) == 1


def test_ensure_topics_does_nothing_when_all_exist():
    admin = FakeAdmin(existing={"a"})

    ensure_topics(admin, [TopicSpec("a")])

    assert admin.created == []


def test_ensure_topics_raises_any_other_error():
    admin = FakeAdmin(errors={"a": KafkaError.INVALID_CONFIG})

    with pytest.raises(KafkaException):
        ensure_topics(admin, [TopicSpec("a")])
