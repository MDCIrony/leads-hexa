from abc import ABC, abstractmethod

from application.ports.output.unit_of_work import UnitOfWorkPort


class ProjectMemberInputPort(ABC):
    @abstractmethod
    def apply(self, tenant_id: str | None, payload: dict, uow: UnitOfWorkPort) -> bool:
        """Projects an agent event; True when it changed the stored member."""
