import logging
import threading
from types import SimpleNamespace

import pytest
from confluent_kafka import KafkaError, KafkaException

from chassis.consumer import TopicSpec, ensure_topics, ensure_topics_until_ready


class FakeFuture:
    def __init__(self, error=None, value=None):
        self.error, self.value = error, value

    def result(self, timeout=None):
        if self.error:
            raise KafkaException(KafkaError(self.error))
        return self.value


class FakeAdmin:
    """`existing` maps a topic name to (partition count, config dict)."""

    def __init__(self, existing=None, errors=None, describe_error=None):
        self.existing, self.errors, self.describe_error = existing or {}, errors or {}, describe_error
        self.created, self.described = [], []

    def list_topics(self, timeout=None):
        return SimpleNamespace(topics={
            name: SimpleNamespace(partitions={i: None for i in range(count)})
            for name, (count, _) in self.existing.items()
        })

    def describe_configs(self, resources):
        self.described.extend(resource.name for resource in resources)
        if self.describe_error:
            raise self.describe_error
        return {
            resource: FakeFuture(value={k: SimpleNamespace(value=v)
                                        for k, v in self.existing[resource.name][1].items()})
            for resource in resources
        }

    def create_topics(self, new_topics, request_timeout=None):
        self.created.extend(new_topics)
        return {t.topic: FakeFuture(self.errors.get(t.topic)) for t in new_topics}


class NoWaitEvent(threading.Event):
    """Skips the backoff sleep so the retry path runs instantly."""

    def wait(self, timeout=None):
        return self.is_set()


class FlakyAdmin:
    def __init__(self, failures, topics):
        self.failures, self.topics = failures, topics

    def list_topics(self, timeout):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("broker unavailable")
        return SimpleNamespace(topics={
            name: SimpleNamespace(partitions={i: None for i in range(3)}) for name in self.topics
        })


def test_ensure_topics_creates_only_what_is_missing():
    admin = FakeAdmin({"a": (3, {})})

    ensure_topics(admin, [TopicSpec("a"), TopicSpec("b", partitions=1, config={"cleanup.policy": "compact"})])

    (created,) = admin.created
    assert (created.topic, created.num_partitions, created.config) == ("b", 1, {"cleanup.policy": "compact"})


def test_ensure_topics_ignores_a_topic_created_in_the_meantime():
    admin = FakeAdmin(errors={"a": KafkaError.TOPIC_ALREADY_EXISTS})

    ensure_topics(admin, [TopicSpec("a")])

    assert len(admin.created) == 1


def test_ensure_topics_does_nothing_when_all_exist():
    admin = FakeAdmin({"a": (3, {})})

    ensure_topics(admin, [TopicSpec("a")])

    assert admin.created == []


def test_ensure_topics_raises_any_other_error():
    admin = FakeAdmin(errors={"a": KafkaError.INVALID_CONFIG})

    with pytest.raises(KafkaException):
        ensure_topics(admin, [TopicSpec("a")])


def test_an_existing_topic_with_other_config_warns_and_is_not_touched(caplog):
    admin = FakeAdmin({"t": (3, {"cleanup.policy": "delete"})})

    with caplog.at_level(logging.WARNING, logger="chassis.consumer"):
        ensure_topics(admin, [TopicSpec("t", config={"cleanup.policy": "compact"})])

    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert "t" in record.getMessage() and "compact" in record.getMessage()
    assert "delete" in record.getMessage()
    assert admin.created == []


def test_an_existing_topic_with_other_partitions_warns(caplog):
    admin = FakeAdmin({"t": (1, {})})

    with caplog.at_level(logging.WARNING, logger="chassis.consumer"):
        ensure_topics(admin, [TopicSpec("t", partitions=3)])

    (record,) = caplog.records
    assert "partitions" in record.getMessage() and "3" in record.getMessage()


def test_a_matching_topic_leaves_no_warning(caplog):
    admin = FakeAdmin({"t": (3, {"cleanup.policy": "compact", "retention.ms": "1"})})

    with caplog.at_level(logging.WARNING, logger="chassis.consumer"):
        ensure_topics(admin, [TopicSpec("t", config={"cleanup.policy": "compact", "retention.ms": "1"})])

    assert caplog.records == []
    assert admin.described == ["t"]


def test_a_failing_describe_configs_warns_and_does_not_raise(caplog):
    admin = FakeAdmin({"t": (3, {})}, describe_error=RuntimeError("acl"))

    with caplog.at_level(logging.WARNING, logger="chassis.consumer"):
        ensure_topics(admin, [TopicSpec("t", config={"cleanup.policy": "compact"})])

    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_topics_are_retried_until_kafka_answers_and_only_then_activated():
    specs = [TopicSpec("internal.a"), TopicSpec("internal.b")]
    admin = FlakyAdmin(failures=2, topics={"internal.a", "internal.b"})
    activated = []

    ready = ensure_topics_until_ready(admin, specs, NoWaitEvent(), lambda: activated.append(True))

    assert ready is True
    assert admin.failures == 0
    assert activated == [True]


def test_a_stop_during_the_retries_never_activates_the_channel():
    stop = NoWaitEvent()
    activated, attempts = [], []

    class StopsAfterFirstFailure(FlakyAdmin):
        def list_topics(self, timeout):
            attempts.append(1)
            stop.set()
            raise RuntimeError("broker unavailable")

    ready = ensure_topics_until_ready(
        StopsAfterFirstFailure(0, set()), [TopicSpec("internal.a")], stop, lambda: activated.append(True),
    )

    assert ready is False
    assert activated == []
    # Stopped on the first backoff, not retried until the broker answered.
    assert len(attempts) == 1
