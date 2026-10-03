from abc import ABC, abstractmethod
from typing import Optional

from application.ports.output.unit_of_work_port import UnitOfWorkPort


class ProjectAdvisorInputPort(ABC):
    @abstractmethod
    def apply(self, tenant_id: Optional[str], payload: dict, uow: UnitOfWorkPort) -> bool:
        """Projects an agent state event; True when it changed the stored advisor."""
