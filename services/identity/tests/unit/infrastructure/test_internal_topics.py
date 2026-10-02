import uuid
from datetime import datetime, timezone

import pytest
from chassis.outbox import OutboxRow

from infrastructure.adapters.output.events.internal_topics import INTERNAL_TOPIC_SPECS, topic_for


def _row(event_type: str) -> OutboxRow:
    return OutboxRow(
        id=uuid.uuid4(), channel="internal", tenant_id=None, partition_key="k",
        event_type=event_type, payload={}, occurred_on=datetime.now(timezone.utc), correlation_id=None,
    )


@pytest.mark.parametrize(
    ("event_type", "topic"),
    [("AgentState", "internal.identity.agents"), ("TenantState", "internal.identity.tenants")],
)
def test_each_identity_state_goes_to_its_own_topic(event_type, topic):
    assert topic_for(_row(event_type)) == topic


@pytest.mark.parametrize("event_type", ["LeadAssigned", "IntakeRejected", "", "agentstate"])
def test_any_other_event_type_is_refused(event_type):
    with pytest.raises(ValueError, match="No internal topic"):
        topic_for(_row(event_type))


def test_every_routed_topic_is_declared_compacted_with_three_partitions():
    declared = {spec.name: spec for spec in INTERNAL_TOPIC_SPECS}

    assert set(declared) == {"internal.identity.agents", "internal.identity.tenants"}
    for spec in declared.values():
        assert spec.partitions == 3
        assert dict(spec.config) == {"cleanup.policy": "compact"}
