"""Kafka consumer loop with bounded retries and a dead-letter topic per group."""
import logging
import threading
import time
from typing import Callable, Sequence

from chassis.consumer.envelope import Envelope
from chassis.consumer.kafka import publish_dead_letter, raise_if_fatal
from chassis.consumer.topics import dlq_topic
from chassis.web import request_id_var

_LOGGER = logging.getLogger(__name__)


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
        # (topic, partition) -> offset of an unsettled message whose rewind failed.
        self._blocked: dict[tuple[str, int], int] = {}

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
                    raise_if_fatal(error)
                    continue
                partition = (message.topic(), message.partition())
                blocked_at = self._blocked.get(partition)
                if blocked_at is not None and message.offset() > blocked_at:
                    # An earlier message of this partition is unsettled and its rewind
                    # failed: committing this one would commit past it and lose it.
                    self._seek(partition, blocked_at)
                    stop.wait(self._rewind_delay_seconds)
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
                    if self._seek(partition, message.offset()):
                        self._blocked.pop(partition, None)
                    else:
                        self._blocked[partition] = message.offset()
                    # Longer than a poll: the dead-letter topic is down, not busy.
                    stop.wait(self._rewind_delay_seconds)
                else:
                    if blocked_at is not None and message.offset() == blocked_at:
                        del self._blocked[partition]
        finally:
            self._consumer.close()

    def _seek(self, partition: tuple[str, int], offset: int) -> bool:
        """Returns whether the consumer now sits at `offset`."""
        from confluent_kafka import TopicPartition

        try:
            self._consumer.seek(TopicPartition(*partition, offset))
            return True
        except Exception:
            # A thread that dies here is never restarted; the caller blocks the
            # partition and keeps polling instead.
            _LOGGER.error("Rewind failed for %s[%s]@%s", *partition, offset, exc_info=True)
            return False

    def _commit(self, message) -> None:
        self._consumer.commit(message=message, asynchronous=False)

    def _dead_letter(self, message, error: str, attempts: int) -> str:
        publish_dead_letter(self._dlq_producer, dlq_topic(self._group), message, error, attempts,
                            self._flush_timeout_seconds)
        # Only once the DLQ has the message: an unconfirmed one would be lost
        # for good if the offset moved on.
        self._commit(message)
        return "dead-lettered"
