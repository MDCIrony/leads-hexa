from typing import Callable
from uuid import UUID

from application.ports.output.advisors.advisor_directory_port import AdvisorDirectoryPort
from application.ports.output.advisors.identity_agents_port import IdentityAgentsPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.advisors.advisor import Advisor
from domain.exceptions import DomainException


class HydratingAdvisorDirectory(AdvisorDirectoryPort):
    """The advisors projection, filled on demand when an agent's event has not arrived yet.

    Each lookup runs in a short transaction of its own, so a hydrated row is
    committed before the caller's transaction relies on it."""

    def __init__(self, unit_of_work: Callable[[], UnitOfWorkPort], identity: IdentityAgentsPort) -> None:
        self._unit_of_work = unit_of_work
        self._identity = identity

    def get(self, agent_id: UUID, tenant_id: UUID) -> Advisor:
        with self._unit_of_work() as uow:
            advisor = uow.advisors.get(agent_id, tenant_id)
        if advisor is None:
            advisor = self._hydrate(agent_id, tenant_id)
        if advisor is None or not advisor.is_routable:
            raise DomainException("El asesor no existe", error_code="AGENT_NOT_FOUND")
        return advisor

    def _hydrate(self, agent_id: UUID, tenant_id: UUID):
        fetched = self._identity.fetch(agent_id)
        if fetched is None:
            return None
        with self._unit_of_work() as uow:
            # The consumer's own version-gated write: whichever arrives second,
            # event or hydration, cannot undo a newer state.
            uow.advisors.upsert_identity(fetched)
            # Re-read rather than trust `fetched`: the stored row may be newer,
            # and an agent of another organization reads back as missing.
            return uow.advisors.get(agent_id, tenant_id)
