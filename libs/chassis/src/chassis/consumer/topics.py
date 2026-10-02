import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

_LOGGER = logging.getLogger(__name__)

DLQ_PREFIX = "internal.dlq."
_MAX_BACKOFF_SECONDS = 30.0


def dlq_topic(group: str) -> str:
    return DLQ_PREFIX + group


@dataclass(frozen=True)
class TopicSpec:
    name: str
    partitions: int = 3
    config: Mapping[str, str] = field(default_factory=dict)


def ensure_topics(admin, specs: Sequence[TopicSpec], timeout_seconds: float = 10.0) -> None:
    """Idempotent: an existing topic is left alone (TOPIC_ALREADY_EXISTS ignored).

    An existing topic that differs from its spec only logs a WARNING: changing
    partitions or retention under live consumers is an operator decision."""
    from confluent_kafka import KafkaError, KafkaException
    from confluent_kafka.admin import NewTopic

    existing = admin.list_topics(timeout=timeout_seconds).topics
    _warn_on_drift(admin, [spec for spec in specs if spec.name in existing], existing, timeout_seconds)
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


def _warn_on_drift(admin, specs: Sequence[TopicSpec], existing, timeout_seconds: float) -> None:
    from confluent_kafka.admin import ConfigResource

    found_partitions = {spec.name: len(existing[spec.name].partitions) for spec in specs}
    found_config: dict[str, Mapping[str, str]] = {}
    configured = [spec for spec in specs if spec.config]
    if configured:
        try:
            futures = admin.describe_configs([ConfigResource("topic", spec.name) for spec in configured])
            for resource, future in futures.items():
                found_config[resource.name] = {k: entry.value for k, entry in future.result(timeout_seconds).items()}
        except Exception as exc:
            # The check is advisory: a broker that cannot describe must not stop startup.
            _LOGGER.warning("Could not verify the configuration of %s (%s)",
                            ", ".join(spec.name for spec in configured), exc)
    for spec in specs:
        drift = []
        if found_partitions[spec.name] != spec.partitions:
            drift.append(f"partitions expected {spec.partitions}, found {found_partitions[spec.name]}")
        found = found_config.get(spec.name, {})
        drift += [f"{key} expected {value!r}, found {found[key]!r}"
                  for key, value in spec.config.items() if key in found and found[key] != value]
        if drift:
            _LOGGER.warning("Topic %s differs from its spec: %s", spec.name, "; ".join(drift))


def ensure_topics_until_ready(
    admin,
    specs: Sequence[TopicSpec],
    stop: threading.Event,
    on_ready: Callable[[], None],
) -> bool:
    """Retries with backoff until the topics exist; returns False if stopped first.

    A broker that is down must not take the process with it (ADR-0026): the
    product relay keeps running meanwhile."""
    delay = 1.0
    while not stop.is_set():
        try:
            ensure_topics(admin, specs)
        except Exception as exc:
            _LOGGER.warning("Kafka topics not ready (%s), retrying in %.0fs", exc, delay)
            _LOGGER.debug("Kafka topics not ready", exc_info=True)
            if stop.wait(delay):
                return False
            delay = min(delay * 2, _MAX_BACKOFF_SECONDS)
        else:
            _LOGGER.info("Kafka topics ensured: %s", ", ".join(spec.name for spec in specs))
            on_ready()
            return True
    return False
