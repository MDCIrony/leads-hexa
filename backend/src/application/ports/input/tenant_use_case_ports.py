from abc import ABC, abstractmethod

from application.dtos.commands import TenantsPageResult, TenantWithManagerResult, UpdateTenantCommand, CreateTenantCommand
from application.dtos.queries import GetTenantsQuery
from domain.entities.tenant import Tenant


class CreateTenantInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateTenantCommand) -> TenantWithManagerResult:
        pass


class GetTenantsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetTenantsQuery) -> TenantsPageResult:
        pass


class UpdateTenantInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateTenantCommand) -> Tenant:
        pass
