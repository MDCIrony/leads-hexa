import json

from chassis.outbox import OutboxRow
from confluent_kafka import Producer


class KafkaOutboundDispatcher:
    """Publishes the outbound channel to the tenant's own topic (ADR-0026).

    One topic per tenant keeps organizations isolated without a consumer-side
    tenant_id filter; lead_id as the partition key keeps everything about one
    lead in order within it."""

    def __init__(self, producer: Producer, flush_timeout_seconds: float = 10.0) -> None:
        self._producer = producer
        self._flush_timeout_seconds = flush_timeout_seconds

    def dispatch(self, row: OutboxRow) -> None:
        delivery_error = None

        def _on_delivery(err, _msg):
            nonlocal delivery_error
            if err is not None:
                delivery_error = err

        self._producer.produce(
            topic=f"leads.{row.tenant_id}",
            key=row.partition_key.encode(),
            value=json.dumps(row.payload).encode(),
            headers=[("event_type", row.event_type.encode())],
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
            raise RuntimeError(f"Kafka delivery failed for topic leads.{row.tenant_id}: {delivery_error}")
