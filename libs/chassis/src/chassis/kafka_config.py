"""Client settings shared by every service that talks to Kafka."""


def producer_config(bootstrap_servers: str, auto_create_topics: bool = True) -> dict:
    config = {
        "bootstrap.servers": bootstrap_servers,
        "acks": "all",
        "enable.idempotence": True,
        # Strictly below the dispatchers' 10 s flush: a message the producer is
        # still retrying when flush gives up must not be delivered after its
        # row was marked failed.
        "message.timeout.ms": 9_000,
    }
    if not auto_create_topics:
        # Internal topics are created by ensure_topics with their retention and
        # compaction; a topic lost later must fail loudly, not come back
        # uncompacted through broker auto-creation.
        config["allow.auto.create.topics"] = False
    return config


def consumer_config(bootstrap_servers: str, group: str) -> dict:
    """Settings the ConsumerLoop requires: manual commits and a new group reading from the start."""
    return {
        "bootstrap.servers": bootstrap_servers,
        "group.id": group,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
        # A group subscribed before the producer creates its topic must see it
        # within seconds, not after the 5-minute default.
        "topic.metadata.refresh.interval.ms": 10_000,
    }
