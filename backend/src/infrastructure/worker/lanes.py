import logging

from chassis.consumer import ConsumerLoop, dlq_topic
from chassis.kafka_config import consumer_config, producer_config
from confluent_kafka import Consumer, Producer

from infrastructure.adapters.input.events.notification_consumer import NotificationConsumer
from infrastructure.di.container import Container

_LOGGER = logging.getLogger(__name__)


def consumer_loop(container: Container, bootstrap_servers: str, group: str, topic: str) -> ConsumerLoop:
    _LOGGER.info("Consumer group %s subscribing to %s (dead letters: %s)", group, topic, dlq_topic(group))
    return ConsumerLoop(
        Consumer(consumer_config(bootstrap_servers, group)),
        Producer(producer_config(bootstrap_servers, auto_create_topics=False)),
        group,
        [topic],
        NotificationConsumer(container.unit_of_work, group),
    )
