import logging
from dataclasses import dataclass, field
from typing import Mapping, Sequence

_LOGGER = logging.getLogger(__name__)

DLQ_PREFIX = "internal.dlq."


def dlq_topic(group: str) -> str:
    return DLQ_PREFIX + group


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
