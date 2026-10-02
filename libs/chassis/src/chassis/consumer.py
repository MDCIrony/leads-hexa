"""Kafka consumer loop with bounded retries and a dead-letter topic per group.

No broker library is imported at module level: the consumer and producers are
injected. confluent-kafka is needed only by ensure_topics and the seek in run,
and is imported there."""
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, Sequence
from uuid import UUID

from chassis.web import request_id_var

_LOGGER = logging.getLogger(__name__)

DLQ_PREFIX = "internal.dlq."


def dlq_topic(group: str) -> str:
    return DLQ_PREFIX + group


@dataclass(frozen=True)
class Envelope:
    event_id: UUID
    event_type: str
    schema_version: int
    occurred_at: str
    producer: str
    tenant_id: Optional[str]
    aggregate_id: str
    correlation_id: Optional[str]
    payload: dict

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Envelope":
        """Raises ValueError on anything that is not a well-formed envelope."""
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("envelope is not a JSON object")
            strings = {k: body[k] for k in ("event_type", "occurred_at", "producer", "aggregate_id")}
            optional = {k: body[k] for k in ("tenant_id", "correlation_id")}
            version, payload = body["schema_version"], body["payload"]
            if not all(isinstance(v, str) for v in strings.values()):
                raise ValueError("envelope string field has the wrong type")
            if not all(v is None or isinstance(v, str) for v in optional.values()):
                raise ValueError("envelope optional field has the wrong type")
            if isinstance(version, bool) or not isinstance(version, int):
                raise ValueError("schema_version is not an integer")
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            return cls(event_id=UUID(body["event_id"]), schema_version=version,
                       payload=payload, **strings, **optional)
        except (KeyError, TypeError, AttributeError, UnicodeDecodeError, RecursionError) as exc:
            # json.JSONDecodeError and the UUID error are already ValueErrors.
            # RecursionError: deeply nested input such as b"[" * 100000 would
            # otherwise escape, and a poison message would block its partition.
            raise ValueError(f"malformed envelope: {exc!r}") from exc


@dataclass(frozen=True)
class TopicSpec:
    name: str
    partitions: int = 3
    config: Mapping[str, str] = field(default_factory=dict)


def ensure_topics(admin, specs: Sequence[TopicSpec], timeout_seconds: float = 10.0) -> None:
    """Idempotent: an existing topic is left alone (TOPIC_ALREADY_EXISTS ignored)."""
    from confluent_kafka import KafkaError, KafkaException
    from confluent_kafka.admin import NewTopic

    existing = admin.list_topics(timeout=timeout_seconds).topics
    missing = [
        # -1 asks the broker for its default replication factor, so the same
        # specs work on the single-broker dev stack and on a real cluster.
        NewTopic(spec.name, num_partitions=spec.partitions, replication_factor=-1,
                 config=dict(spec.config))
        for spec in specs if spec.name not in existing
    ]
    if not missing:
        return
    for topic, future in admin.create_topics(missing, request_timeout=timeout_seconds).items():
        try:
            future.result(timeout_seconds)
        except KafkaException as exc:
            # Another instance may have created it between the listing and now.
            if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                raise
            _LOGGER.debug("Topic %s already exists", topic)


class ConsumerLoop:
    """At-least-once consumption: handle, retry with backoff, dead-letter, then commit.

    The consumer passed in must be created with `enable.auto.commit=false` (this
    loop commits each offset itself, after the outcome is durable) and
    `auto.offset.reset=earliest` (a new group reads the topic from its start).
    `handle` must be idempotent: a message can be delivered more than once."""

    def __init__(
        self,
        consumer,
        dlq_producer,
        group: str,
        topics: Sequence[str],
        handle: Callable[[Envelope], None],
        max_attempts: int = 3,
        backoff_seconds: Sequence[float] = (0.2, 0.5, 1.0),
        sleep: Callable[[float], None] = time.sleep,
        flush_timeout_seconds: float = 10.0,
        rewind_delay_seconds: float = 1.0,
    ) -> None:
        self._consumer = consumer
        self._dlq_producer = dlq_producer
        self._group = group
        self._topics = list(topics)
        self._handle = handle
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._flush_timeout_seconds = flush_timeout_seconds
        self._rewind_delay_seconds = rewind_delay_seconds

    def process(self, message) -> str:
        """Returns "handled" or "dead-lettered"; the offset is committed either way.

        Raises, without committing, if the dead-letter topic cannot be written."""
        try:
            envelope = Envelope.from_bytes(message.value())
        except ValueError as exc:
            # Retrying cannot fix bytes that do not parse.
            return self._dead_letter(message, str(exc), attempts=0)

        error = ""
        for attempt in range(1, self._max_attempts + 1):
            token = request_id_var.set(envelope.correlation_id) if envelope.correlation_id else None
            try:
                self._handle(envelope)
            except Exception as exc:
                error = str(exc)
                _LOGGER.warning("Attempt %d/%d failed for event %s", attempt, self._max_attempts,
                                envelope.event_id, exc_info=True)
            else:
                self._commit(message)
                return "handled"
            finally:
                if token is not None:
                    request_id_var.reset(token)
            if attempt < self._max_attempts and self._backoff_seconds:
                self._sleep(self._backoff_seconds[min(attempt, len(self._backoff_seconds)) - 1])
        return self._dead_letter(message, error, attempts=self._max_attempts)

    def run(self, stop: threading.Event, poll_timeout: float = 1.0) -> None:
        self._consumer.subscribe(self._topics)
        try:
            while not stop.is_set():
                message = self._consumer.poll(poll_timeout)
                if message is None:
                    continue
                error = message.error()
                if error:
                    self._log_consumer_error(error)
                    continue
                try:
                    self.process(message)
                except Exception:
                    # The dead-letter topic is unavailable. Not committing is not
                    # enough on its own: the next poll moves on and its commit
                    # would cover this offset too. Rewind so it is redelivered.
                    _LOGGER.error("Message %s[%s]@%s not settled, rewinding",
                                  message.topic(), message.partition(), message.offset(),
                                  exc_info=True)
                    self._rewind(message)
                    # Longer than a poll: the dead-letter topic is down, not busy.
                    stop.wait(self._rewind_delay_seconds)
        finally:
            self._consumer.close()

    @staticmethod
    def _log_consumer_error(error) -> None:
        from confluent_kafka import KafkaError

        # End of a partition is informational; anything else may need attention.
        level = logging.DEBUG if error.code() == KafkaError._PARTITION_EOF else logging.WARNING
        _LOGGER.log(level, "Consumer error: %s", error)

    def _rewind(self, message) -> None:
        from confluent_kafka import TopicPartition

        try:
            self._consumer.seek(TopicPartition(message.topic(), message.partition(), message.offset()))
        except Exception:
            # A thread that dies here is never restarted; keep polling instead.
            _LOGGER.error("Rewind failed for %s[%s]@%s", message.topic(), message.partition(),
                          message.offset(), exc_info=True)

    def _commit(self, message) -> None:
        self._consumer.commit(message=message, asynchronous=False)

    def _dead_letter(self, message, error: str, attempts: int) -> str:
        topic = dlq_topic(self._group)
        delivery_error = None

        def _on_delivery(err, _msg):
            nonlocal delivery_error
            if err is not None:
                delivery_error = err

        self._dlq_producer.produce(
            topic=topic,
            key=message.key(),
            value=message.value(),
            # The original headers (event_type, correlation_id) travel along so a
            # replay from the DLQ keeps its routing context.
            headers=[
                *(message.headers() or []),
                ("error", error.encode()),
                ("original_topic", message.topic().encode()),
                ("original_partition", str(message.partition()).encode()),
                ("original_offset", str(message.offset()).encode()),
                ("attempts", str(attempts).encode()),
            ],
            on_delivery=_on_delivery,
        )
        pending = self._dlq_producer.flush(self._flush_timeout_seconds)
        if pending > 0:
            raise RuntimeError(f"DLQ flush timed out with {pending} message(s) undelivered")
        if delivery_error is not None:
            raise RuntimeError(f"DLQ delivery failed for topic {topic}: {delivery_error}")
        # Only once the DLQ has the message: an unconfirmed one would be lost
        # for good if the offset moved on.
        self._commit(message)
        return "dead-lettered"
