from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from application.dtos.commands import (
    CreateAssignmentRuleCommand, CreateDisqualificationRuleCommand, CreateScoringRuleCommand,
    UpdateAssignmentRuleCommand, UpdateDisqualificationRuleCommand, UpdateScoringRuleCommand,
)
from application.dtos.context import RequestContext
from application.dtos.queries import GetAssignmentRulesQuery, GetDisqualificationRulesQuery, GetRulesQuery
from application.ports.input.rule_use_case_ports import (
    CreateAssignmentRuleInputPort, CreateScoringRuleInputPort, DeleteAssignmentRuleInputPort,
    DeleteScoringRuleInputPort, GetAssignmentRulesInputPort, GetScoringRulesInputPort,
    UpdateAssignmentRuleInputPort, UpdateScoringRuleInputPort,
)
from application.ports.input.disqualification_rule_use_case_ports import (
    CreateDisqualificationRuleInputPort, DeleteDisqualificationRuleInputPort,
    GetDisqualificationRulesInputPort, UpdateDisqualificationRuleInputPort,
)
from domain.entities.disqualification_rule import DisqualificationRule
from domain.entities.rule import AssignmentRule, ScoringRule
from infrastructure.adapters.input.api.dependencies import (
    get_create_scoring_rule_use_case, get_get_scoring_rules_use_case,
    get_update_scoring_rule_use_case, get_delete_scoring_rule_use_case,
    get_create_assignment_rule_use_case, get_get_assignment_rules_use_case,
    get_update_assignment_rule_use_case, get_delete_assignment_rule_use_case,
    get_create_disqualification_rule_use_case, get_get_disqualification_rules_use_case,
    get_update_disqualification_rule_use_case, get_delete_disqualification_rule_use_case,
    require_organization_manager,
)
from infrastructure.adapters.input.api.schemas import (
    AssignmentRuleCreate, AssignmentRuleResponse, AssignmentRuleUpdate, PaginatedAssignmentRulesResponse,
    CriterionSchema, ScoringRuleCreate, ScoringRuleResponse, ScoringRuleUpdate, PaginatedScoringRulesResponse,
    DisqualificationRuleCreate, DisqualificationRuleResponse, DisqualificationRuleUpdate,
    PaginatedDisqualificationRulesResponse,
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
