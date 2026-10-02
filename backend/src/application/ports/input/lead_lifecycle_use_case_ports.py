from abc import ABC, abstractmethod

from application.dtos.commands import AssignLeadCommand, DiscardLeadCommand, LeadsPageResult
from application.dtos.queries import GetLeadQuery, GetMyLeadsQuery
from domain.leads.lead import Lead


class AssignLeadInputPort(ABC):
    @abstractmethod
    def execute(self, command: AssignLeadCommand) -> Lead:
        pass


class DiscardLeadInputPort(ABC):
    @abstractmethod
    def execute(self, command: DiscardLeadCommand) -> Lead:
        pass


class GetMyLeadsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetMyLeadsQuery) -> LeadsPageResult:
        pass


class GetLeadInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadQuery) -> Lead:
        pass
