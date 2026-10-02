from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.context import RequestContext
from application.dtos.tenants import CreateTenantCommand, GetTenantsQuery, UpdateTenantCommand
from application.ports.input.tenants import CreateTenantInputPort, GetTenantsInputPort, UpdateTenantInputPort
from domain.tenants.tenant import Tenant
from infrastructure.adapters.input.api.agents.schemas import AgentResponse, to_agent_response
from infrastructure.adapters.input.api.dependencies import require_platform_admin
from infrastructure.adapters.input.api.tenants.schemas import (
    PaginatedTenantsResponse, TenantCreate, TenantResponse, TenantUpdate,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_create_tenant_use_case, get_get_tenants_use_case, get_update_tenant_use_case,
)

router = APIRouter()


def _to_response(
    tenant: Tenant, agent_count: int | None = None, manager: AgentResponse | None = None
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
    result = use_case.execute(CreateTenantCommand(
        name=request.name,
        manager_name=request.manager.name,
        manager_email=request.manager.email,
        manager_password=request.manager.password,
    ))
    return _to_response(result.tenant, manager=to_agent_response(result.manager))


@router.get("", response_model=PaginatedTenantsResponse)
@router.get("/", response_model=PaginatedTenantsResponse, include_in_schema=False)
def list_tenants(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetTenantsInputPort = Depends(get_get_tenants_use_case),
    context: RequestContext = Depends(require_platform_admin),
):
    page = use_case.execute(GetTenantsQuery(limit=limit, offset=offset))
    items = [_to_response(summary.tenant, agent_count=summary.agent_count) for summary in page.items]
    return PaginatedTenantsResponse(
        items=items, total=page.total, limit=limit, offset=offset, has_more=(offset + len(items)) < page.total,
    )


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: UUID,
    request: TenantUpdate,
    use_case: UpdateTenantInputPort = Depends(get_update_tenant_use_case),
    context: RequestContext = Depends(require_platform_admin),
):
    tenant = use_case.execute(UpdateTenantCommand(tenant_id=tenant_id, name=request.name, is_active=request.is_active))
    return _to_response(tenant)
