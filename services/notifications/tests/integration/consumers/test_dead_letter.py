from uuid import uuid4

from chassis.consumer import ConsumerLoop, Envelope, dlq_topic

from application.use_cases.notifications.notification_handler import NotificationHandler
from infrastructure.adapters.input.consumers.notification_consumer import NotificationConsumer

from .events import count, event_bytes

_GROUP = "notifications.lead-events"
_TOPIC = "internal.lead-core.events"


class _Message:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def value(self): return self._value
    def key(self): return b"lead"
    def topic(self): return _TOPIC
    def partition(self): return 1
    def offset(self): return 7
    def headers(self): return [("event_type", b"LeadAssigned")]


class _Consumer:
    def __init__(self) -> None:
        self.commits = []

    def commit(self, **kwargs):
        self.commits.append(kwargs)


class _Producer:
    def __init__(self) -> None:
        self.produced = []

    def produce(self, **kwargs):
        self.produced.append(kwargs)
        kwargs["on_delivery"](None, None)

    def flush(self, timeout):
        return 0


def test_an_event_whose_effect_always_fails_is_dead_lettered_and_committed(test_db, uow_factory, monkeypatch):
    message = _Message(event_bytes("LeadAssigned", uuid4(), {"lead_id": str(uuid4()), "agent_id": str(uuid4())}))
    attempts = []

    def boom(self, *args):
        attempts.append(args)
        raise RuntimeError("effect failed")

    monkeypatch.setattr(NotificationHandler, "apply", boom)
    consumer, producer = _Consumer(), _Producer()
    loop = ConsumerLoop(consumer, producer, _GROUP, [_TOPIC], NotificationConsumer(uow_factory, _GROUP),
                        sleep=lambda _: None)

    assert loop.process(message) == "dead-lettered"

    assert len(attempts) == 3
    (sent,) = producer.produced
    assert sent["topic"] == dlq_topic(_GROUP) == "internal.dlq.notifications.lead-events"
    assert dict(sent["headers"])["attempts"] == b"3"
    assert sent["value"] == message.value()
    # Committed, so the partition moves on instead of replaying the poison message.
    assert consumer.commits == [{"message": message, "asynchronous": False}]
    assert count(test_db, "SELECT COUNT(*) AS n FROM notifications") == 0
    assert count(test_db, "SELECT COUNT(*) AS n FROM processed_events WHERE event_id = %s",
                 (Envelope.from_bytes(message.value()).event_id,)) == 0
