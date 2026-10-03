from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status

from application.dtos.commands import CreateSalesGroupCommand, UpdateSalesGroupCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetSalesGroupsQuery
from application.ports.input.groups.sales_group_use_case_ports import (
    CreateSalesGroupInputPort, DeleteSalesGroupInputPort, GetSalesGroupsInputPort,
    UpdateSalesGroupInputPort,
)
from domain.groups.sales_group import SalesGroup
from infrastructure.adapters.input.api.dependencies import (
    get_create_sales_group_use_case, get_delete_sales_group_use_case,
    get_get_sales_groups_use_case, get_update_sales_group_use_case,
    require_organization_manager,
)
from infrastructure.adapters.input.api.schemas import (
    PaginatedGroupsResponse, SalesGroupCreate, SalesGroupResponse, SalesGroupUpdate,
)

router = APIRouter()


def _to_response(group: SalesGroup, agent_count: Optional[int] = None) -> SalesGroupResponse:
    return SalesGroupResponse(
        id=str(group.id),
        name=group.name,
        description=group.description,
        default_strategy=group.default_strategy.value,
        capacity_per_agent=group.capacity_per_agent,
        is_active=group.is_active,
        agent_count=agent_count,
    )


@router.post("", response_model=SalesGroupResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SalesGroupResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_group(
    request: SalesGroupCreate,
    use_case: CreateSalesGroupInputPort = Depends(get_create_sales_group_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = CreateSalesGroupCommand(
        tenant_id=context.tenant_id,
        name=request.name,
        description=request.description,
        default_strategy=request.default_strategy.value,
        capacity_per_agent=request.capacity_per_agent,
    )
    return _to_response(use_case.execute(command))


@router.get("", response_model=PaginatedGroupsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedGroupsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_groups(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetSalesGroupsInputPort = Depends(get_get_sales_groups_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    query = GetSalesGroupsQuery(tenant_id=context.tenant_id, limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [_to_response(summary.group, agent_count=summary.agent_count) for summary in page.items]
    return PaginatedGroupsResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
    )


@router.patch("/{group_id}", response_model=SalesGroupResponse, status_code=status.HTTP_200_OK)
def update_group(
    group_id: UUID,
    request: SalesGroupUpdate,
    use_case: UpdateSalesGroupInputPort = Depends(get_update_sales_group_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = UpdateSalesGroupCommand(
        tenant_id=context.tenant_id,
        group_id=group_id,
        name=request.name,
        description=request.description,
        default_strategy=request.default_strategy.value if request.default_strategy else None,
        capacity_per_agent=request.capacity_per_agent,
        is_active=request.is_active,
    )
    return _to_response(use_case.execute(command))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: UUID,
    use_case: DeleteSalesGroupInputPort = Depends(get_delete_sales_group_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    use_case.execute(tenant_id=context.tenant_id, group_id=group_id)
