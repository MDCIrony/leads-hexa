from abc import ABC, abstractmethod
from typing import List
from application.dtos.queries import GetLeadsQuery
from domain.entities.lead import Lead

class GetLeadsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadsQuery) -> List[Lead]:
        pass
