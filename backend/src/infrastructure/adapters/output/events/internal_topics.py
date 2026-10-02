"""Where each internal event travels, and the topics that must exist for it.

Only the topics this producer writes: each consumer declares its own dead letters."""
from chassis.consumer import TopicSpec
from chassis.outbox import OutboxRow

_SEVEN_DAYS_MS = str(7 * 24 * 60 * 60 * 1000)
_EVENTS = {"cleanup.policy": "delete", "retention.ms": _SEVEN_DAYS_MS}
# Compacted: only the latest state per key matters to whoever rebuilds a copy.
_STATE = {"cleanup.policy": "compact"}

_TOPIC_BY_EVENT_TYPE = {
    "LeadAssigned": "internal.lead-core.events",
    "LeadReassigned": "internal.lead-core.events",
    "LeadLeftUnassigned": "internal.lead-core.events",
    "IntakeRejected": "internal.intake.events",
    "AgentState": "internal.identity.agents",
    "TenantState": "internal.identity.tenants",
}

INTERNAL_TOPIC_SPECS: list[TopicSpec] = [
    TopicSpec("internal.lead-core.events", 3, _EVENTS),
    TopicSpec("internal.intake.events", 3, _EVENTS),
    TopicSpec("internal.identity.agents", 3, _STATE),
    TopicSpec("internal.identity.tenants", 3, _STATE),
]


def topic_for(row: OutboxRow) -> str:
    try:
        return _TOPIC_BY_EVENT_TYPE[row.event_type]
    except KeyError:
        # Failing loudly beats guessing: a row on the wrong topic reaches
        # consumers that silently skip it, and nobody learns it was lost.
        raise ValueError(f"No internal topic for event type {row.event_type!r}") from None
