from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.context import RequestContext
from application.dtos.rules import CreateScoringRuleCommand, GetRulesQuery, UpdateScoringRuleCommand
from application.ports.input.rules.rule_use_case_ports import (
    CreateScoringRuleInputPort, DeleteScoringRuleInputPort, GetScoringRulesInputPort,
    UpdateScoringRuleInputPort,
)
from domain.rules.scoring_rule import ScoringRule
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.rules.schemas import (
    CriterionSchema, PaginatedScoringRulesResponse, ScoringRuleCreate, ScoringRuleResponse,
    ScoringRuleUpdate,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_create_scoring_rule_use_case, get_delete_scoring_rule_use_case,
    get_get_scoring_rules_use_case, get_update_scoring_rule_use_case,
)

router = APIRouter()

def _to_scoring_response(rule: ScoringRule) -> ScoringRuleResponse:
    return ScoringRuleResponse(
        id=str(rule.id),
        name=rule.name,
        conditions=[CriterionSchema(**c.as_dict()) for c in rule.conditions],
        score_delta=rule.score_delta,
        priority=rule.priority,
        is_active=rule.is_active,
    )


@router.post("/scoring", response_model=ScoringRuleResponse, status_code=status.HTTP_201_CREATED)
def create_scoring_rule(
    request: ScoringRuleCreate,
    use_case: CreateScoringRuleInputPort = Depends(get_create_scoring_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = CreateScoringRuleCommand(
        tenant_id=context.tenant_id,
        name=request.name,
        conditions=[c.model_dump() for c in request.conditions],
        score_delta=request.score_delta,
        priority=request.priority,
        is_active=request.is_active,
    )
    saved = use_case.execute(command)
    return _to_scoring_response(saved)

@router.get("/scoring", response_model=PaginatedScoringRulesResponse, status_code=status.HTTP_200_OK)
def list_scoring_rules(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetScoringRulesInputPort = Depends(get_get_scoring_rules_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    query = GetRulesQuery(tenant_id=context.tenant_id, limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [_to_scoring_response(r) for r in page.items]
    return PaginatedScoringRulesResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
    )


@router.patch("/scoring/{rule_id}", response_model=ScoringRuleResponse, status_code=status.HTTP_200_OK)
def update_scoring_rule(
    rule_id: UUID,
    request: ScoringRuleUpdate,
    use_case: UpdateScoringRuleInputPort = Depends(get_update_scoring_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = UpdateScoringRuleCommand(
        tenant_id=context.tenant_id,
        rule_id=rule_id,
        name=request.name,
        conditions=[c.model_dump() for c in request.conditions] if request.conditions is not None else None,
        score_delta=request.score_delta,
        priority=request.priority,
        is_active=request.is_active,
    )
    return _to_scoring_response(use_case.execute(command))


@router.delete("/scoring/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scoring_rule(
    rule_id: UUID,
    use_case: DeleteScoringRuleInputPort = Depends(get_delete_scoring_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    use_case.execute(tenant_id=context.tenant_id, rule_id=rule_id)
