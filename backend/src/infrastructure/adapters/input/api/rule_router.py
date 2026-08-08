from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from application.dtos.commands import CreateAssignmentRuleCommand, CreateScoringRuleCommand, UpdateAssignmentRuleCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetAssignmentRulesQuery, GetRulesQuery
from application.ports.input.rule_use_case_ports import (
    CreateAssignmentRuleInputPort, CreateScoringRuleInputPort, DeleteAssignmentRuleInputPort,
    GetAssignmentRulesInputPort, GetScoringRulesInputPort, UpdateAssignmentRuleInputPort,
)
from domain.entities.rule import AssignmentRule
from infrastructure.adapters.input.api.dependencies import (
    get_create_scoring_rule_use_case, get_get_scoring_rules_use_case,
    get_create_assignment_rule_use_case, get_get_assignment_rules_use_case,
    get_update_assignment_rule_use_case, get_delete_assignment_rule_use_case,
    require_organization_manager,
)
from infrastructure.adapters.input.api.schemas import (
    AssignmentRuleCreate, AssignmentRuleResponse, AssignmentRuleUpdate, PaginatedAssignmentRulesResponse,
    ScoringRuleCreate, ScoringRuleResponse,
)

router = APIRouter()

@router.post("/scoring", response_model=ScoringRuleResponse, status_code=status.HTTP_201_CREATED)
def create_scoring_rule(
    request: ScoringRuleCreate,
    use_case: CreateScoringRuleInputPort = Depends(get_create_scoring_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = CreateScoringRuleCommand(
        tenant_id=context.tenant_id,
        name=request.name,
        field=request.field,
        operator=request.operator.value if hasattr(request.operator, 'value') else str(request.operator),
        value=str(request.value),
        score_delta=request.score_delta,
    )
    saved = use_case.execute(command)
    return ScoringRuleResponse(
        id=str(saved.id),
        name=saved.name,
        field=saved.field,
        operator=saved.operator.value,
        value=saved.value,
        score_delta=saved.score_delta,
    )

@router.get("/scoring", response_model=List[ScoringRuleResponse], status_code=status.HTTP_200_OK)
def list_scoring_rules(
    use_case: GetScoringRulesInputPort = Depends(get_get_scoring_rules_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    query = GetRulesQuery(tenant_id=context.tenant_id)
    rules = use_case.execute(query)
    return [
        ScoringRuleResponse(
            id=str(r.id),
            name=r.name,
            field=r.field,
            operator=r.operator.value,
            value=r.value,
            score_delta=r.score_delta,
        )
        for r in rules
    ]


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
    )
    return _to_response(use_case.execute(command))


@router.get("/assignment", response_model=PaginatedAssignmentRulesResponse, status_code=status.HTTP_200_OK)
def list_assignment_rules(
    use_case: GetAssignmentRulesInputPort = Depends(get_get_assignment_rules_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    rules = use_case.execute(GetAssignmentRulesQuery(tenant_id=context.tenant_id))
    items = [_to_response(r) for r in rules]
    # The use case has no pagination of its own — every rule is loaded on
    # every ingestion anyway — so this page is simply "everything, at once".
    return PaginatedAssignmentRulesResponse(
        items=items,
        total=len(items),
        limit=len(items) or 100,
        offset=0,
        has_more=False,
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
    )
    return _to_response(use_case.execute(command))


@router.delete("/assignment/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment_rule(
    rule_id: UUID,
    use_case: DeleteAssignmentRuleInputPort = Depends(get_delete_assignment_rule_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    use_case.execute(tenant_id=context.tenant_id, rule_id=rule_id)
