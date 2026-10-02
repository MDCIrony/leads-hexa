from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.context import RequestContext
from application.dtos.sources import CreateLeadSourceCommand, GetLeadSourcesQuery, UpdateLeadSourceCommand
from application.ports.input.sources import (
    CreateLeadSourceInputPort,
    DeleteLeadSourceInputPort,
    GetLeadSourcesInputPort,
    UpdateLeadSourceInputPort,
)
from domain.sources.lead_source import LeadSource
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.sources.schemas import (
    LeadSourceCreate,
    LeadSourceResponse,
    LeadSourceUpdate,
    PaginatedSourcesResponse,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_create_lead_source_use_case,
    get_delete_lead_source_use_case,
    get_get_lead_sources_use_case,
    get_update_lead_source_use_case,
)

router = APIRouter()


def _to_response(source: LeadSource) -> LeadSourceResponse:
    return LeadSourceResponse(
        id=str(source.id),
        name=source.name,
        kind=source.kind.value,
        field_mapping=source.field_mapping,
        is_active=source.is_active,
        created_at=source.created_at,
    )


@router.post("", response_model=LeadSourceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=LeadSourceResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_source(
    request: LeadSourceCreate,
    use_case: CreateLeadSourceInputPort = Depends(get_create_lead_source_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = CreateLeadSourceCommand(
        tenant_id=context.tenant_id, name=request.name, kind=request.kind.value, field_mapping=request.field_mapping,
    )
    return _to_response(use_case.execute(command))


@router.get("", response_model=PaginatedSourcesResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedSourcesResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_sources(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetLeadSourcesInputPort = Depends(get_get_lead_sources_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    page = use_case.execute(GetLeadSourcesQuery(tenant_id=context.tenant_id, limit=limit, offset=offset))
    items = [_to_response(source) for source in page.items]
    return PaginatedSourcesResponse(
        items=items, total=page.total, limit=limit, offset=offset, has_more=(offset + len(items)) < page.total,
    )


@router.patch("/{source_id}", response_model=LeadSourceResponse, status_code=status.HTTP_200_OK)
def update_source(
    source_id: UUID,
    request: LeadSourceUpdate,
    use_case: UpdateLeadSourceInputPort = Depends(get_update_lead_source_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = UpdateLeadSourceCommand(
        tenant_id=context.tenant_id, source_id=source_id,
        name=request.name, field_mapping=request.field_mapping, is_active=request.is_active,
    )
    return _to_response(use_case.execute(command))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: UUID,
    use_case: DeleteLeadSourceInputPort = Depends(get_delete_lead_source_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    use_case.execute(tenant_id=context.tenant_id, source_id=source_id)
