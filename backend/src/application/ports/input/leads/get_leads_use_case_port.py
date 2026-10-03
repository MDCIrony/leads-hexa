from abc import ABC, abstractmethod
from application.dtos.leads import GetLeadsQuery, LeadsPageResult

class GetLeadsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadsQuery) -> LeadsPageResult:
        pass
