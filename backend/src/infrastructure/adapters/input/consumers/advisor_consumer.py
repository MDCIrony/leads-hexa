from collections.abc import Callable

from chassis.consumer import Envelope

from application.ports.input.advisors.project_advisor_port import ProjectAdvisorInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.advisors.project_advisor import ProjectAdvisorUseCase


class AdvisorConsumer:
    """Keeps the advisors projection current from the agent state topic.

    Does not use `processed_events`: the upsert is gated on `version` in SQL
    (the use case's check is only the fast path), so a redelivered, reordered
    or concurrent older event changes nothing."""

    def __init__(self, uow_factory: Callable[[], UnitOfWorkPort]) -> None:
        self._uow_factory = uow_factory
        self._project: ProjectAdvisorInputPort = ProjectAdvisorUseCase()

    def __call__(self, envelope: Envelope) -> None:
        if envelope.event_type != "AgentState":
            return
        with self._uow_factory() as uow:
            self._project.apply(envelope.tenant_id, envelope.payload, uow)
