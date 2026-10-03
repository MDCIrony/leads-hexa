import json
import uuid

from chassis.outbox import OutboxRow

from domain.leads.lead import Lead
from domain.events.lead_events import LeadProcessedEvent
from domain.value_objects.enums import LeadStatus
from domain.value_objects.score_breakdown import AppliedRule
from infrastructure.adapters.output.events.kafka_outbound_dispatcher import (
    KafkaOutboundDispatcher,
)

_TENANT = uuid.uuid4()
_SOURCE = uuid.uuid4()
_RULE = uuid.uuid4()


class _FakeProducer:
    """Stands in for confluent_kafka.Producer: records what it was asked to
    send, and drives the on_delivery callback the way flush() would."""

    def __init__(self, delivery_error=None):
        self.produced = []
        self.flush_timeout = None
        self._delivery_error = delivery_error
        self._on_delivery = None

    def produce(self, topic, key, value, headers, on_delivery):
        self.produced.append({"topic": topic, "key": key, "value": value, "headers": headers})
        self._on_delivery = on_delivery

    def flush(self, timeout):
        self.flush_timeout = timeout
        if self._on_delivery is not None:
            self._on_delivery(self._delivery_error, None)
        return 0


def _qualified_lead() -> Lead:
    return Lead.create(
        tenant_id=_TENANT,
        source_id=_SOURCE,
        first_name="Jane",
        last_name="Doe",
        email="test@example.com",
        phone="+34600000000",
        company="Acme Corp",
        budget="15000.50",
        industry="Tech",
        custom_attributes={"utm_source": "linkedin"},
        score=75,
        score_breakdown=[AppliedRule(rule_id=_RULE, name="Presupuesto alto", score_delta=75)],
        status=LeadStatus.QUALIFIED,
    )


def _entry_of(event) -> OutboxRow:
    """Exactly what the relay reads back out of the outbox."""
    return OutboxRow(
        id=event.event_id,
        channel="product",
        tenant_id=event.tenant_id,
        partition_key=event.partition_key,
        event_type=event.event_type,
        payload=event.as_payload(),
        occurred_on=event.occurred_on,
        correlation_id=None,
    )


def test_publishes_to_the_tenant_topic_keyed_by_lead_id():
    lead = _qualified_lead()
    entry = _entry_of(LeadProcessedEvent.of(lead))
    producer = _FakeProducer()
    dispatcher = KafkaOutboundDispatcher(producer)

    dispatcher.dispatch(entry)

    assert len(producer.produced) == 1
    sent = producer.produced[0]
    assert sent["topic"] == f"leads.{_TENANT}"
    assert sent["key"] == str(lead.id).encode()
    assert sent["headers"] == [("event_type", b"LeadProcessedEvent")]
    assert json.loads(sent["value"]) == entry.payload
    assert producer.flush_timeout is not None


def test_a_delivery_failure_raises_so_the_relay_can_retry():
    """The relay marks an entry published when dispatch returns without
    raising. A completed-with-error delivery must not look like success."""
    lead = _qualified_lead()
    entry = _entry_of(LeadProcessedEvent.of(lead))
    producer = _FakeProducer(delivery_error="broker not available")
    dispatcher = KafkaOutboundDispatcher(producer)

    try:
        dispatcher.dispatch(entry)
    except RuntimeError:
        return
    raise AssertionError("dispatch must raise when Kafka delivery failed")


def test_a_flush_timeout_with_undelivered_messages_raises():
    """flush() returning a nonzero count means delivery was never confirmed
    within the deadline — treated the same as an outright failure."""

    class _TimingOutProducer(_FakeProducer):
        def flush(self, timeout):
            self.flush_timeout = timeout
            return 3

    lead = _qualified_lead()
    entry = _entry_of(LeadProcessedEvent.of(lead))
    dispatcher = KafkaOutboundDispatcher(_TimingOutProducer())

    try:
        dispatcher.dispatch(entry)
    except RuntimeError:
        return
    raise AssertionError("dispatch must raise when flush times out with messages pending")
