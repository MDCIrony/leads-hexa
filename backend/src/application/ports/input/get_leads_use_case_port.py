from abc import ABC, abstractmethod
from application.dtos.queries import GetLeadsQuery
from application.dtos.commands import LeadsPageResult

class GetLeadsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadsQuery) -> LeadsPageResult:
        pass
