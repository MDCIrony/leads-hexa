from domain.events.lead_events import LeadProcessedEvent
from domain.value_objects.enums import LeadStatus
from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher


def _explode(event: LeadProcessedEvent) -> None:
    raise RuntimeError("boom")


def _event() -> LeadProcessedEvent:
    return LeadProcessedEvent(
        tenant_id="t-1",
        lead_id="l-1",
        email="lead@test.com",
        score=35,
        status=LeadStatus.ASSIGNED,
        assigned_agent_id="a-1",
    )


def test_a_failing_handler_does_not_stop_the_others():
    seen = []
    publisher = InMemoryEventPublisher()
    publisher.subscribe(LeadProcessedEvent, _explode)
    publisher.subscribe(LeadProcessedEvent, lambda event: seen.append(event))

    publisher.publish(_event())

    assert len(seen) == 1


def test_a_failing_handler_does_not_propagate_to_the_caller():
    """The lead is already committed by the time events are published, so a
    handler error must not surface as a failed ingestion."""
    publisher = InMemoryEventPublisher()
    publisher.subscribe(LeadProcessedEvent, _explode)

    publisher.publish(_event())
