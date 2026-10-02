"""Kafka consumption with bounded retries and a dead-letter topic per group.

No broker library is imported at module level: the consumer and producers are
injected. confluent-kafka is needed only by the topic checks, the seek and the
error check, and is imported there."""
from chassis.consumer.envelope import Envelope
from chassis.consumer.lane import run_consumer_lane
from chassis.consumer.loop import ConsumerLoop
from chassis.consumer.topics import DLQ_PREFIX, TopicSpec, dlq_topic, ensure_topics, ensure_topics_until_ready

__all__ = ["DLQ_PREFIX", "ConsumerLoop", "Envelope", "TopicSpec", "dlq_topic", "ensure_topics",
           "ensure_topics_until_ready", "run_consumer_lane"]
