from domain.events.lead_events import LeadProcessedEvent
from domain.value_objects.enums import LeadStatus


def test_lead_processed_event_creation() -> None:
    event = LeadProcessedEvent(
        tenant_id="tenant-1",
        lead_id="lead-1",
        email="test@example.com",
        score=50,
        status=LeadStatus.QUALIFIED,
        assigned_agent_id="agent-1",
    )
    assert event.event_type == "LeadProcessedEvent"
    assert event.event_id is not None
    assert event.occurred_on is not None
    assert event.tenant_id == "tenant-1"
