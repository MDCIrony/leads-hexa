from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status

from application.dtos.commands import CreateTenantCommand, UpdateTenantCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetTenantsQuery
from application.ports.input.tenant_use_case_ports import (
    CreateTenantInputPort, GetTenantsInputPort, UpdateTenantInputPort
)
from domain.entities.tenant import Tenant
from infrastructure.adapters.input.api.dependencies import (
    get_create_tenant_use_case, get_get_tenants_use_case, get_update_tenant_use_case,
    require_platform_admin,
)
from infrastructure.adapters.input.api.schemas import (
    AgentResponse, TenantCreate, TenantUpdate, TenantResponse, PaginatedTenantsResponse,
)

router = APIRouter()


def _to_response(
    tenant: Tenant,
    agent_count: Optional[int] = None,
    manager: Optional[AgentResponse] = None,
) -> TenantResponse:
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat(),
        agent_count=agent_count,
        manager=manager,
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_tenant(
    request: TenantCreate,
    use_case: CreateTenantInputPort = Depends(get_create_tenant_use_case),
    context: RequestContext = Depends(require_platform_admin),
):
    command = CreateTenantCommand(
        name=request.name,
        manager_name=request.manager.name,
        manager_email=request.manager.email,
        manager_password=request.manager.password,
    )
    result = use_case.execute(command)
    manager = AgentResponse(
        id=str(result.manager.id),
        name=result.manager.name,
        email=result.manager.email,
        team=result.manager.team,
        active_leads_count=result.manager.active_leads_count,
        is_active=result.manager.is_active,
        role=result.manager.role.value,
        tenant_id=str(result.manager.tenant_id),
    )
    return _to_response(result.tenant, manager=manager)


@router.get("", response_model=PaginatedTenantsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedTenantsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_tenants(
    limit: int = 100,
    offset: int = 0,
    use_case: GetTenantsInputPort = Depends(get_get_tenants_use_case),
    context: RequestContext = Depends(require_platform_admin),
):
    query = GetTenantsQuery(limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [_to_response(summary.tenant, agent_count=summary.agent_count) for summary in page.items]
    return PaginatedTenantsResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
    )


@router.patch("/{tenant_id}", response_model=TenantResponse, status_code=status.HTTP_200_OK)
def update_tenant(
    tenant_id: UUID,
    request: TenantUpdate,
    use_case: UpdateTenantInputPort = Depends(get_update_tenant_use_case),
    context: RequestContext = Depends(require_platform_admin),
):
    command = UpdateTenantCommand(tenant_id=tenant_id, name=request.name, is_active=request.is_active)
    tenant = use_case.execute(command)
    return _to_response(tenant)
