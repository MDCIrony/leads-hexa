"""The Kafka client calls the loop makes, kept apart so the loop reads as retry and commit logic."""
import logging

_LOGGER = logging.getLogger(__name__)


def publish_dead_letter(producer, topic: str, message, error: str, attempts: int,
                        flush_timeout_seconds: float) -> None:
    """Copies the message to `topic` and waits for the broker; raises if it is not confirmed."""
    delivery_error = None

    def _on_delivery(err, _msg):
        nonlocal delivery_error
        if err is not None:
            delivery_error = err

    producer.produce(
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
    pending = producer.flush(flush_timeout_seconds)
    if pending > 0:
        raise RuntimeError(f"DLQ flush timed out with {pending} message(s) undelivered")
    if delivery_error is not None:
        raise RuntimeError(f"DLQ delivery failed for topic {topic}: {delivery_error}")


def raise_if_fatal(error) -> None:
    from confluent_kafka import KafkaError, KafkaException

    if error.fatal():
        # The client cannot recover from a fatal error; let the caller see it
        # instead of polling a dead consumer forever.
        raise KafkaException(error)
    # End of a partition is informational; anything else may need attention.
    level = logging.DEBUG if error.code() == KafkaError._PARTITION_EOF else logging.WARNING
    _LOGGER.log(level, "Consumer error: %s", error)


def rewind(consumer, partition: tuple[str, int], offset: int) -> bool:
    """Returns whether the consumer now sits at `offset`."""
    from confluent_kafka import TopicPartition

    try:
        consumer.seek(TopicPartition(*partition, offset))
        return True
    except Exception:
        # A thread that dies here is never restarted; the caller blocks the
        # partition and keeps polling instead.
        _LOGGER.error("Rewind failed for %s[%s]@%s", *partition, offset, exc_info=True)
        return False


def shut_down(consumer, dlq_producer, flush_timeout_seconds: float) -> None:
    """Releases the consumer and the DLQ producer; one failing never skips the next step."""
    steps = [consumer.close, lambda: dlq_producer.flush(flush_timeout_seconds)]
    if hasattr(dlq_producer, "close"):
        steps.append(dlq_producer.close)
    for step in steps:
        try:
            step()
        except Exception:
            _LOGGER.warning("Consumer shutdown step failed", exc_info=True)
