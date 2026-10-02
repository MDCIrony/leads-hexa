from typing import Callable, Optional
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
        # Looked up across organizations on purpose: an agent already projected
        # under another tenant is a local 404, not a reason to ask identity, so
        # tenant isolation never depends on identity being up.
        with self._unit_of_work() as uow:
            advisor = uow.advisors.get_any(agent_id)
        if advisor is None:
            advisor = self._hydrate(agent_id)
        if advisor is None or str(advisor.tenant_id) != str(tenant_id) or not advisor.is_routable:
            raise DomainException("El asesor no existe", error_code="AGENT_NOT_FOUND")
        return advisor

    def _hydrate(self, agent_id: UUID) -> Optional[Advisor]:
        fetched = self._identity.fetch(agent_id)
        if fetched is None:
            return None
        with self._unit_of_work() as uow:
            # The consumer's own version-gated write: whichever arrives second,
            # event or hydration, cannot undo a newer state.
            uow.advisors.upsert_identity(fetched)
            # Re-read rather than trust `fetched`: the stored row may be newer.
            return uow.advisors.get_any(agent_id)
