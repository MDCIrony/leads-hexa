import json
from typing import Callable

from chassis.outbox.envelope import envelope
from chassis.outbox.row import OutboxRow


class KafkaEventDispatcher:
    """Internal events: envelope as value, partition_key as key, event_type and
    correlation_id as headers. Delivery confirmed through the callback + flush,
    same as the product dispatcher today.

    The producer must be created with `acks=all` and `enable.idempotence=true`
    (no loss on a leader change, no duplicates from internal retries), and with
    `message.timeout.ms` close to `flush_timeout_seconds`, so a message the
    producer is still retrying is not delivered after the row was marked failed."""

    def __init__(
        self,
        producer,
        producer_name: str,
        topic_for: Callable[[OutboxRow], str],
        flush_timeout_seconds: float = 10.0,
    ) -> None:
        self._producer = producer
        self._producer_name = producer_name
        self._topic_for = topic_for
        self._flush_timeout_seconds = flush_timeout_seconds

    def dispatch(self, row: OutboxRow) -> None:
        topic = self._topic_for(row)
        delivery_error = None

        def _on_delivery(err, _msg):
            nonlocal delivery_error
            if err is not None:
                delivery_error = err

        headers = [("event_type", row.event_type.encode())]
        if row.correlation_id:
            headers.append(("correlation_id", row.correlation_id.encode()))
        self._producer.produce(
            topic=topic,
            key=row.partition_key.encode(),
            value=json.dumps(envelope(row, self._producer_name)).encode(),
            headers=headers,
            on_delivery=_on_delivery,
        )
        # flush(), not poll(): the relay marks the row published the moment
        # dispatch() returns without raising. flush()'s return value alone
        # cannot tell success from a completed-with-error delivery, so
        # failure is read from the delivery callback it drives instead.
        pending = self._producer.flush(self._flush_timeout_seconds)
        if pending > 0:
            raise RuntimeError(f"Kafka flush timed out with {pending} message(s) undelivered")
        if delivery_error is not None:
            raise RuntimeError(f"Kafka delivery failed for topic {topic}: {delivery_error}")
