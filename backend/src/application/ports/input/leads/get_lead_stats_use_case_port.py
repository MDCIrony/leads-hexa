from abc import ABC, abstractmethod
from application.dtos.leads import GetLeadStatsQuery, LeadStatsResult

class GetLeadStatsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadStatsQuery) -> LeadStatsResult:
        pass
