import uuid
from datetime import datetime, timezone

import pytest
from chassis.outbox import OutboxRow

from infrastructure.adapters.output.events.internal_topics import INTERNAL_TOPIC_SPECS, topic_for


def _row(event_type: str) -> OutboxRow:
    return OutboxRow(
        id=uuid.uuid4(), channel="internal", tenant_id=None, partition_key="k", event_type=event_type,
        payload={}, occurred_on=datetime.now(timezone.utc), correlation_id=None,
    )


def test_intake_rejected_goes_to_the_intake_events_topic():
    assert topic_for(_row("IntakeRejected")) == "internal.intake.events"


def test_the_topic_is_one_the_producer_declares():
    assert {spec.name for spec in INTERNAL_TOPIC_SPECS} == {"internal.intake.events"}


def test_an_unknown_event_type_fails_loudly():
    with pytest.raises(ValueError, match="LeadAssigned"):
        topic_for(_row("LeadAssigned"))
