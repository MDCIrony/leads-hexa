from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.context import RequestContext
from application.dtos.rules import (
    CreateDisqualificationRuleCommand, GetDisqualificationRulesQuery, UpdateDisqualificationRuleCommand,
)
from application.ports.input.rules.disqualification_rule_use_case_ports import (
    CreateDisqualificationRuleInputPort, DeleteDisqualificationRuleInputPort,
    GetDisqualificationRulesInputPort, UpdateDisqualificationRuleInputPort,
)
from domain.rules.disqualification_rule import DisqualificationRule
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.rules.schemas import (
    CriterionSchema, DisqualificationRuleCreate, DisqualificationRuleResponse,
    DisqualificationRuleUpdate, PaginatedDisqualificationRulesResponse,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_create_disqualification_rule_use_case, get_delete_disqualification_rule_use_case,
    get_get_disqualification_rules_use_case, get_update_disqualification_rule_use_case,
)

router = APIRouter()

def _to_disqualification_response(rule: DisqualificationRule) -> DisqualificationRuleResponse:
    return DisqualificationRuleResponse(
        id=str(rule.id),
        name=rule.name,
        conditions=[CriterionSchema(**c.as_dict()) for c in rule.conditions],
        priority=rule.priority,
        is_active=rule.is_active,
    )


@router.post(
    "/disqualification", response_model=DisqualificationRuleResponse, status_code=status.HTTP_201_CREATED
)
def create_disqualification_rule(
    request: DisqualificationRuleCreate,
    use_case: CreateDisqualificationRuleInputPort = Depends(get_create_disqualification_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = CreateDisqualificationRuleCommand(
        tenant_id=context.tenant_id,
        name=request.name,
        conditions=[c.model_dump() for c in request.conditions],
        priority=request.priority,
        is_active=request.is_active,
    )
    return _to_disqualification_response(use_case.execute(command))


@router.get(
    "/disqualification",
    response_model=PaginatedDisqualificationRulesResponse,
    status_code=status.HTTP_200_OK,
)
def list_disqualification_rules(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetDisqualificationRulesInputPort = Depends(get_get_disqualification_rules_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    query = GetDisqualificationRulesQuery(tenant_id=context.tenant_id, limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [_to_disqualification_response(r) for r in page.items]
    return PaginatedDisqualificationRulesResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
    )


@router.patch(
    "/disqualification/{rule_id}", response_model=DisqualificationRuleResponse, status_code=status.HTTP_200_OK
)
def update_disqualification_rule(
    rule_id: UUID,
    request: DisqualificationRuleUpdate,
    use_case: UpdateDisqualificationRuleInputPort = Depends(get_update_disqualification_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = UpdateDisqualificationRuleCommand(
        tenant_id=context.tenant_id,
        rule_id=rule_id,
        name=request.name,
        conditions=[c.model_dump() for c in request.conditions] if request.conditions is not None else None,
        priority=request.priority,
        is_active=request.is_active,
    )
    return _to_disqualification_response(use_case.execute(command))


@router.delete("/disqualification/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disqualification_rule(
    rule_id: UUID,
    use_case: DeleteDisqualificationRuleInputPort = Depends(get_delete_disqualification_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    use_case.execute(tenant_id=context.tenant_id, rule_id=rule_id)
