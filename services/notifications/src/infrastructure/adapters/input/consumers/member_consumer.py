from collections.abc import Callable

from chassis.consumer import Envelope

from application.ports.input.members import ProjectMemberInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.members.project_member import ProjectMemberUseCase


class MemberConsumer:
    """Keeps the member projection current from the agent state topic.

    Does not use `processed_events`: the version-gated upsert is already
    idempotent, and a redelivered or reordered event changes nothing."""

    def __init__(self, uow_factory: Callable[[], UnitOfWorkPort]) -> None:
        self._uow_factory = uow_factory
        self._project: ProjectMemberInputPort = ProjectMemberUseCase()

    def __call__(self, envelope: Envelope) -> None:
        if envelope.event_type != "AgentState":
            return
        with self._uow_factory() as uow:
            self._project.apply(envelope.tenant_id, envelope.payload, uow)
