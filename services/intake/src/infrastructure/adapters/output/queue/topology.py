QUEUE_NAME = "intake.jobs"
DLQ_NAME = "intake.jobs.dlq"

# A quorum queue is what makes the count native: RabbitMQ dead-letters a
# message itself once its own delivery counter passes this, instead of the
# application tracking attempts through the x-death header by hand.
_MAX_DELIVERIES = 3


def declare_intake_topology(channel) -> None:
    """Declared identically by the relay and the worker: RabbitMQ rejects a
    redeclare of the same queue with mismatched arguments."""
    channel.queue_declare(queue=DLQ_NAME, durable=True)
    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": _MAX_DELIVERIES,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": DLQ_NAME,
        },
    )
