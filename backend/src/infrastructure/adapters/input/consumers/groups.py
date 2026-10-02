"""Which topic each consumer group reads, and the dead-letter topics this service declares."""
from collections.abc import Callable

from chassis.consumer import Envelope, TopicSpec, dlq_topic

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.input.consumers.advisor_consumer import AdvisorConsumer
from infrastructure.adapters.input.consumers.intake.tenant_consumer import TenantConsumer

ADVISORS_GROUP = "lead-core.advisors"
# Intake code living in the monolith until F4 extracts it.
INTAKE_TENANTS_GROUP = "intake.tenants"

CONSUMER_GROUPS: dict[str, str] = {
    ADVISORS_GROUP: "internal.identity.agents",
    INTAKE_TENANTS_GROUP: "internal.identity.tenants",
}

_SEVEN_DAYS_MS = str(7 * 24 * 60 * 60 * 1000)

# The consumer declares its own dead-letter topics; the producers own the topics it reads.
DLQ_TOPIC_SPECS: list[TopicSpec] = [
    TopicSpec(dlq_topic(group), 1, {"cleanup.policy": "delete", "retention.ms": _SEVEN_DAYS_MS})
    for group in CONSUMER_GROUPS
]


def handler_for(group: str, uow_factory: Callable[[], UnitOfWorkPort]) -> Callable[[Envelope], None]:
    if group == ADVISORS_GROUP:
        return AdvisorConsumer(uow_factory)
    if group == INTAKE_TENANTS_GROUP:
        return TenantConsumer(uow_factory, group)
    raise ValueError(f"No handler for consumer group {group!r}")
