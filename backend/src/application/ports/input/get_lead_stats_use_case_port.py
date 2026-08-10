from abc import ABC, abstractmethod
from application.dtos.queries import GetLeadStatsQuery
from application.dtos.commands import LeadStatsResult

class GetLeadStatsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadStatsQuery) -> LeadStatsResult:
        pass
