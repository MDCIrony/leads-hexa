from abc import ABC, abstractmethod

from application.dtos.tenants import (
    CreateTenantCommand,
    GetTenantsQuery,
    TenantsPageResult,
    TenantWithManagerResult,
    UpdateTenantCommand,
)
from domain.tenants.tenant import Tenant


class CreateTenantInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateTenantCommand) -> TenantWithManagerResult: ...


class GetTenantsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetTenantsQuery) -> TenantsPageResult: ...


class UpdateTenantInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateTenantCommand) -> Tenant: ...
