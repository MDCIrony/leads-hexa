# What every service of this platform that publishes calls itself; in F1 only
# the monolith writes, so this process publishes on its behalf.
PRODUCER_NAME = "lead-core"


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
