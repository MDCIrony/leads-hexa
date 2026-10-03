from abc import ABC, abstractmethod

from application.dtos.advisors import AdvisorsPage, AdvisorView, ListAdvisorsQuery, SetAdvisorGroupCommand


class ListAdvisorsInputPort(ABC):
    @abstractmethod
    def execute(self, query: ListAdvisorsQuery) -> AdvisorsPage: ...


class SetAdvisorGroupInputPort(ABC):
    @abstractmethod
    def execute(self, command: SetAdvisorGroupCommand) -> AdvisorView: ...
