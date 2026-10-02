"""Which topic each consumer group reads, and the dead-letter topics this service declares."""
from collections.abc import Callable

from chassis.consumer import Envelope, TopicSpec, dlq_topic

from application.ports.output.unit_of_work import UnitOfWorkPort
from infrastructure.adapters.input.consumers.member_consumer import MemberConsumer
from infrastructure.adapters.input.consumers.notification_consumer import NotificationConsumer

MEMBERS_GROUP = "notifications.members"

CONSUMER_GROUPS: dict[str, str] = {
    "notifications.lead-events": "internal.lead-core.events",
    "notifications.intake-events": "internal.intake.events",
    MEMBERS_GROUP: "internal.identity.agents",
}

_SEVEN_DAYS_MS = str(7 * 24 * 60 * 60 * 1000)

# The consumer declares its own dead-letter topics; the producers own the topics it reads.
DLQ_TOPIC_SPECS: list[TopicSpec] = [
    TopicSpec(dlq_topic(group), 1, {"cleanup.policy": "delete", "retention.ms": _SEVEN_DAYS_MS})
    for group in CONSUMER_GROUPS
]


def handler_for(group: str, uow_factory: Callable[[], UnitOfWorkPort]) -> Callable[[Envelope], None]:
    if group == MEMBERS_GROUP:
        return MemberConsumer(uow_factory)
    return NotificationConsumer(uow_factory, group)
