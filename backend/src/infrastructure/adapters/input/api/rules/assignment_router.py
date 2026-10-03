from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.context import RequestContext
from application.dtos.rules import (
    CreateAssignmentRuleCommand, GetAssignmentRulesQuery, UpdateAssignmentRuleCommand,
)
from application.ports.input.rules.rule_use_case_ports import (
    CreateAssignmentRuleInputPort, DeleteAssignmentRuleInputPort, GetAssignmentRulesInputPort,
    UpdateAssignmentRuleInputPort,
)
from domain.rules.assignment_rule import AssignmentRule
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.rules.schemas import (
    AssignmentRuleCreate, AssignmentRuleResponse, AssignmentRuleUpdate, CriterionSchema,
    PaginatedAssignmentRulesResponse,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_create_assignment_rule_use_case, get_delete_assignment_rule_use_case,
    get_get_assignment_rules_use_case, get_update_assignment_rule_use_case,
)

router = APIRouter()

def _to_response(rule: AssignmentRule) -> AssignmentRuleResponse:
    return AssignmentRuleResponse(
        id=str(rule.id),
        name=rule.name,
        min_score=rule.min_score,
        max_score=rule.max_score,
        target_group_id=str(rule.target_group_id) if rule.target_group_id else None,
        target_agent_ids=[str(i) for i in rule.target_agent_ids],
        agent_match_mode=rule.agent_match_mode.value,
        strategy=rule.strategy.value if rule.strategy else None,
        priority=rule.priority,
        is_active=rule.is_active,
        rr_cursor=rule.rr_cursor,
        conditions=[CriterionSchema(**c.as_dict()) for c in rule.conditions],
    )


@router.post("/assignment", response_model=AssignmentRuleResponse, status_code=status.HTTP_201_CREATED)
def create_assignment_rule(
    request: AssignmentRuleCreate,
    use_case: CreateAssignmentRuleInputPort = Depends(get_create_assignment_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = CreateAssignmentRuleCommand(
        tenant_id=context.tenant_id,
        name=request.name,
        min_score=request.min_score,
        max_score=request.max_score,
        target_group_id=request.target_group_id,
        target_agent_ids=request.target_agent_ids,
        agent_match_mode=request.agent_match_mode.value,
        strategy=request.strategy.value if request.strategy else None,
        priority=request.priority,
        conditions=[c.model_dump() for c in request.conditions],
    )
    return _to_response(use_case.execute(command))


@router.get("/assignment", response_model=PaginatedAssignmentRulesResponse, status_code=status.HTTP_200_OK)
def list_assignment_rules(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetAssignmentRulesInputPort = Depends(get_get_assignment_rules_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    # Sliced here rather than in SQL: the assignment-rule repository has no
    # LIMIT/OFFSET, because the assignment engine loads every rule of the
    # organization on each ingestion anyway. The client sees a correct page
    # either way; what it does not get is a smaller query.
    rules = use_case.execute(GetAssignmentRulesQuery(tenant_id=context.tenant_id))
    all_items = [_to_response(r) for r in rules]
    items = all_items[offset:offset + limit]
    return PaginatedAssignmentRulesResponse(
        items=items,
        total=len(all_items),
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < len(all_items),
    )


@router.patch("/assignment/{rule_id}", response_model=AssignmentRuleResponse, status_code=status.HTTP_200_OK)
def update_assignment_rule(
    rule_id: UUID,
    request: AssignmentRuleUpdate,
    use_case: UpdateAssignmentRuleInputPort = Depends(get_update_assignment_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = UpdateAssignmentRuleCommand(
        tenant_id=context.tenant_id,
        rule_id=rule_id,
        name=request.name,
        min_score=request.min_score,
        max_score=request.max_score,
        target_group_id=request.target_group_id,
        target_agent_ids=request.target_agent_ids,
        agent_match_mode=request.agent_match_mode.value if request.agent_match_mode else None,
        strategy=request.strategy.value if request.strategy else None,
        priority=request.priority,
        is_active=request.is_active,
        conditions=[c.model_dump() for c in request.conditions] if request.conditions is not None else None,
    )
    return _to_response(use_case.execute(command))


@router.delete("/assignment/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment_rule(
    rule_id: UUID,
    use_case: DeleteAssignmentRuleInputPort = Depends(get_delete_assignment_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    use_case.execute(tenant_id=context.tenant_id, rule_id=rule_id)
