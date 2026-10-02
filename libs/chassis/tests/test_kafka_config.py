from chassis.kafka_config import consumer_config, producer_config


def test_consumer_config_has_exactly_the_expected_keys():
    assert consumer_config("kafka:9092", "g") == {
        "bootstrap.servers": "kafka:9092",
        "group.id": "g",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
        # A group subscribed before the producer creates its topic must see it
        # within seconds, not after the 5-minute default.
        "topic.metadata.refresh.interval.ms": 10_000,
    }


def test_producer_config_keeps_its_values():
    assert producer_config("kafka:9092") == {
        "bootstrap.servers": "kafka:9092", "acks": "all", "enable.idempotence": True,
        "message.timeout.ms": 9_000,
    }


def test_the_internal_producer_never_auto_creates_topics_and_the_timeout_is_below_the_flush():
    internal = producer_config("kafka:9092", auto_create_topics=False)

    assert internal["allow.auto.create.topics"] is False
    # The dispatchers flush for 10 s.
    assert internal["message.timeout.ms"] < 10_000
