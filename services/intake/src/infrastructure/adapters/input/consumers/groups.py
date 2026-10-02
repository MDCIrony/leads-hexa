"""Which topic each consumer group reads, and the dead-letter topics this service declares."""
from collections.abc import Callable

from chassis.consumer import Envelope, TopicSpec, dlq_topic

from application.ports.output.unit_of_work import UnitOfWorkPort
from infrastructure.adapters.input.consumers.tenant_consumer import TenantConsumer

# Same group the monolith used: the committed offsets and the dead-letter topic carry over.
INTAKE_TENANTS_GROUP = "intake.tenants"

CONSUMER_GROUPS: dict[str, str] = {INTAKE_TENANTS_GROUP: "internal.identity.tenants"}

_SEVEN_DAYS_MS = str(7 * 24 * 60 * 60 * 1000)

# The consumer declares its own dead-letter topics; the producers own the topics it reads.
DLQ_TOPIC_SPECS: list[TopicSpec] = [
    TopicSpec(dlq_topic(group), 1, {"cleanup.policy": "delete", "retention.ms": _SEVEN_DAYS_MS})
    for group in CONSUMER_GROUPS
]


def handler_for(group: str, uow_factory: Callable[[], UnitOfWorkPort]) -> Callable[[Envelope], None]:
    if group == INTAKE_TENANTS_GROUP:
        return TenantConsumer(uow_factory, group)
    raise ValueError(f"No handler for consumer group {group!r}")
