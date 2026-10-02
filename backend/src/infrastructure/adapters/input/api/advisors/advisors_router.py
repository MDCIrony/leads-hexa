from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from application.dtos.advisors import AdvisorView, ListAdvisorsQuery, SetAdvisorGroupCommand
from application.dtos.context import RequestContext
from application.ports.input.advisors.advisor_use_case_ports import ListAdvisorsInputPort, SetAdvisorGroupInputPort
from infrastructure.adapters.input.api.advisors.dependencies import (
    get_list_advisors_use_case, get_set_advisor_group_use_case,
)
from infrastructure.adapters.input.api.advisors.schemas import (
    AdvisorGroupUpdate, AdvisorResponse, AdvisorsPageResponse,
)
from infrastructure.adapters.input.api.dependencies import require_organization_manager

router = APIRouter()


def _to_response(view: AdvisorView) -> AdvisorResponse:
    advisor = view.advisor
    return AdvisorResponse(
        agent_id=str(advisor.agent_id),
        name=advisor.name,
        group_id=str(advisor.group_id) if advisor.group_id else None,
        is_active=advisor.is_active,
        active_load=view.active_load,
    )


@router.get("", response_model=AdvisorsPageResponse)
@router.get("/", response_model=AdvisorsPageResponse, include_in_schema=False)
def list_advisors(
    group_id: Optional[UUID] = None,
    # None lists both: the agent screen joins this page with /agents by agent_id.
    is_active: Optional[bool] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: ListAdvisorsInputPort = Depends(get_list_advisors_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    page = use_case.execute(ListAdvisorsQuery(context.tenant_id, group_id, is_active, limit, offset))
    return AdvisorsPageResponse(items=[_to_response(view) for view in page.items], total=page.total,
                                limit=limit, offset=offset)


@router.patch("/{agent_id}", response_model=AdvisorResponse)
def set_advisor_group(
    agent_id: UUID,
    request: AdvisorGroupUpdate,
    use_case: SetAdvisorGroupInputPort = Depends(get_set_advisor_group_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    return _to_response(use_case.execute(SetAdvisorGroupCommand(context.tenant_id, agent_id, request.group_id)))
