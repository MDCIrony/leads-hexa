from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.groups import (
    CreateSalesGroupCommand,
    GetSalesGroupsQuery,
    SalesGroupsPageResult,
    UpdateSalesGroupCommand,
)
from domain.groups.sales_group import SalesGroup


class CreateSalesGroupInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateSalesGroupCommand) -> SalesGroup:
        pass


class GetSalesGroupsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetSalesGroupsQuery) -> SalesGroupsPageResult:
        pass


class UpdateSalesGroupInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateSalesGroupCommand) -> SalesGroup:
        pass


class DeleteSalesGroupInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, group_id: UUID) -> None:
        pass
