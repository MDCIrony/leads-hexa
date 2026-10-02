import logging
import threading

import pytest
from confluent_kafka import KafkaError, KafkaException

from chassis.consumer import ConsumerLoop, dlq_topic
from chassis.web import request_id_var
from consumer.helpers import GROUP, FakeConsumer, FakeMessage, FakeProducer, raw


def _loop(handle, consumer=None, producer=None, sleeps=None):
    sleeps = [] if sleeps is None else sleeps
    return ConsumerLoop(consumer or FakeConsumer(), producer or FakeProducer(), GROUP,
                        ["internal.lead-core.events"], handle, sleep=sleeps.append,
                        rewind_delay_seconds=0)


def test_a_handled_message_commits_synchronously():
    consumer, handled = FakeConsumer(), []
    message = FakeMessage(raw())

    assert _loop(handled.append, consumer).process(message) == "handled"

    assert len(handled) == 1
    assert consumer.commits == [{"message": message, "asynchronous": False}]


def test_a_handler_that_recovers_commits_once_and_never_dead_letters():
    consumer, producer, sleeps, calls = FakeConsumer(), FakeProducer(), [], []

    def flaky(envelope):
        calls.append(envelope)
        if len(calls) < 3:
            raise RuntimeError("transient")

    assert _loop(flaky, consumer, producer, sleeps).process(FakeMessage(raw())) == "handled"

    assert len(calls) == 3 and sleeps == [0.2, 0.5]
    assert len(consumer.commits) == 1 and producer.produced == []


def test_exhausted_attempts_dead_letter_the_original_message_and_commit():
    consumer, producer, sleeps, calls = FakeConsumer(), FakeProducer(), [], []
    value = raw()
    message = FakeMessage(value)

    def broken(envelope):
        calls.append(envelope)
        raise RuntimeError("boom")

    assert _loop(broken, consumer, producer, sleeps).process(message) == "dead-lettered"

    assert len(calls) == 3
    (sent,) = producer.produced
    assert sent["topic"] == "internal.dlq." + GROUP == dlq_topic(GROUP)
    assert (sent["value"], sent["key"]) == (value, b"lead-9")
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
        _loop(broken, consumer, producer).process(FakeMessage(raw()))

    assert consumer.commits == []


def test_handle_sees_the_envelope_correlation_id_and_it_is_restored():
    seen = []

    _loop(lambda envelope: seen.append(request_id_var.get())).process(FakeMessage(raw(correlation_id="abc")))

    assert seen == ["abc"]
    assert request_id_var.get() == "-"


def test_run_subscribes_processes_until_stopped_and_closes():
    stop, handled = threading.Event(), []
    consumer = FakeConsumer([FakeMessage(raw()), FakeMessage(raw())], stop)

    _loop(handled.append, consumer).run(stop, poll_timeout=0)

    assert consumer.subscribed == ["internal.lead-core.events"]
    assert len(handled) == 2 and len(consumer.commits) == 2 and consumer.closed


def test_run_rewinds_to_the_failed_message_when_the_dlq_is_down(caplog):
    stop = threading.Event()
    consumer = FakeConsumer([FakeMessage(raw(), partition=1, offset=7)], stop)

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
    consumer = FakeConsumer([eof, broken, FakeMessage(raw())], stop)

    with caplog.at_level(logging.DEBUG, logger="chassis.consumer"):
        _loop(handled.append, consumer).run(stop, poll_timeout=0)

    assert len(handled) == 1 and len(consumer.commits) == 1
    levels = {r.levelno for r in caplog.records}
    assert levels == {logging.DEBUG, logging.WARNING}


def _failing_seek(partition):
    raise KafkaException(KafkaError(KafkaError._STATE))


def test_a_failed_rewind_blocks_the_partition_until_the_unsettled_offset_is_redelivered(caplog):
    stop, handled = threading.Event(), []
    first_try = {"fail": True}

    def handle(envelope):
        if first_try["fail"] and envelope.payload["n"] == 7:
            raise RuntimeError("boom")
        handled.append(envelope.payload["n"])

    seven, eight = FakeMessage(raw(payload={"n": 7}), offset=7), FakeMessage(raw(payload={"n": 8}), offset=8)
    consumer = FakeConsumer([seven, eight], stop)
    consumer.seek = _failing_seek
    loop = ConsumerLoop(consumer, FakeProducer(pending=1), GROUP, ["t"], handle,
                        max_attempts=1, rewind_delay_seconds=0)

    with caplog.at_level(logging.CRITICAL):
        loop.run(stop, poll_timeout=0)

    assert consumer.commits == [] and handled == []
    assert loop._blocked == {("internal.lead-core.events", 2): 7}

    # The seek recovers and 7 comes back; with its block cleared, 8 flows again.
    first_try["fail"] = False
    stop = threading.Event()
    consumer.stop, consumer.queue = stop, [seven, eight]
    loop.run(stop, poll_timeout=0)

    assert handled == [7, 8] and len(consumer.commits) == 2
    assert loop._blocked == {}


def test_a_blocked_partition_retries_the_rewind_to_the_blocked_offset(caplog):
    stop = threading.Event()
    consumer = FakeConsumer([FakeMessage(raw(), offset=7), FakeMessage(raw(), offset=8)], stop)
    seeks = []
    consumer.seek = lambda tp: (seeks.append(tp.offset), _failing_seek(tp))
    loop = ConsumerLoop(consumer, FakeProducer(pending=1), GROUP, ["t"], lambda e: 1 / 0,
                        max_attempts=1, rewind_delay_seconds=0)

    with caplog.at_level(logging.CRITICAL):
        loop.run(stop, poll_timeout=0)

    assert seeks == [7, 7]


def test_a_successful_rewind_leaves_no_block():
    stop = threading.Event()
    consumer = FakeConsumer([FakeMessage(raw(), offset=7)], stop)
    loop = ConsumerLoop(consumer, FakeProducer(pending=1), GROUP, ["t"], lambda e: 1 / 0,
                        max_attempts=1, rewind_delay_seconds=0)

    loop.run(stop, poll_timeout=0)

    assert loop._blocked == {} and len(consumer.seeks) == 1


def test_a_fatal_consumer_error_stops_the_loop_and_closes():
    stop = threading.Event()
    consumer = FakeConsumer([FakeMessage(None, error=KafkaError(KafkaError._FATAL, fatal=True))], stop)

    with pytest.raises(KafkaException):
        _loop(lambda e: None, consumer).run(stop, poll_timeout=0)

    assert consumer.closed


def test_run_waits_the_dedicated_delay_after_a_rewind():
    waits = []

    class RecordingStop(threading.Event):
        def wait(self, timeout=None):
            waits.append(timeout)
            return super().wait(0)

    stop = RecordingStop()
    consumer = FakeConsumer([FakeMessage(raw())], stop)
    loop = ConsumerLoop(consumer, FakeProducer(pending=1), GROUP, ["t"], lambda e: 1 / 0,
                        max_attempts=1, sleep=lambda s: None, rewind_delay_seconds=2.5)

    loop.run(stop, poll_timeout=0.1)

    assert waits == [2.5]


@pytest.mark.parametrize("callback", ["on_revoke", "on_lost"])
def test_a_rebalance_unblocks_the_partitions_that_left_this_consumer(callback):
    from confluent_kafka import TopicPartition

    stop = threading.Event()
    consumer = FakeConsumer(stop=stop)
    loop = _loop(lambda e: None, consumer)
    loop.run(stop, poll_timeout=0)
    loop._blocked = {("internal.lead-core.events", 2): 7, ("internal.lead-core.events", 3): 9}

    consumer.callbacks[callback](consumer, [TopicPartition("internal.lead-core.events", 2)])

    assert loop._blocked == {("internal.lead-core.events", 3): 9}


def test_a_subscribe_that_raises_still_closes_the_consumer():
    class Broken(FakeConsumer):
        def subscribe(self, topics, **callbacks):
            raise KafkaException(KafkaError(KafkaError._STATE))

    consumer = Broken()

    with pytest.raises(KafkaException):
        _loop(lambda e: None, consumer).run(threading.Event(), poll_timeout=0)

    assert consumer.closed


def test_run_flushes_and_closes_the_dlq_producer_on_exit():
    stop, producer = threading.Event(), FakeProducer()
    loop = ConsumerLoop(FakeConsumer(stop=stop), producer, GROUP, ["t"], lambda e: None,
                        flush_timeout_seconds=4.0)

    loop.run(stop, poll_timeout=0)

    assert producer.flushes == [4.0] and producer.closed


def test_a_failing_consumer_close_does_not_skip_the_producer_shutdown():
    stop, producer = threading.Event(), FakeProducer()

    class BadClose(FakeConsumer):
        def close(self):
            raise RuntimeError("close failed")

    loop = _loop(lambda e: None, BadClose(stop=stop), producer)

    loop.run(stop, poll_timeout=0)

    assert producer.flushes and producer.closed


def test_a_failing_flush_does_not_skip_the_producer_close():
    stop = threading.Event()

    class BadFlush(FakeProducer):
        def flush(self, timeout):
            raise RuntimeError("flush failed")

    producer = BadFlush()

    _loop(lambda e: None, FakeConsumer(stop=stop), producer).run(stop, poll_timeout=0)

    assert producer.closed


def test_a_producer_without_close_is_tolerated():
    stop = threading.Event()

    class NoClose:
        def flush(self, timeout): return 0

    _loop(lambda e: None, FakeConsumer(stop=stop), NoClose()).run(stop, poll_timeout=0)
