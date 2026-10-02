from abc import ABC, abstractmethod

from application.ports.output.unit_of_work_port import UnitOfWorkPort


class ProvisionTenantSourcesInputPort(ABC):
    @abstractmethod
    def apply(self, payload: dict, uow: UnitOfWorkPort) -> bool:
        """Handles a tenant state event; True when it created the default sources."""
