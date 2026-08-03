from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, status
from application.dtos.commands import CreateScoringRuleCommand, CreateRoutingRuleCommand
from application.dtos.queries import GetRulesQuery
from application.ports.input.rule_use_case_ports import (
    CreateScoringRuleInputPort, GetScoringRulesInputPort,
    CreateRoutingRuleInputPort, GetRoutingRulesInputPort
)
from infrastructure.adapters.input.api.dependencies import (
    get_create_scoring_rule_use_case, get_get_scoring_rules_use_case,
    get_create_routing_rule_use_case, get_get_routing_rules_use_case
)
from infrastructure.adapters.input.api.schemas import (
    ScoringRuleCreate, ScoringRuleResponse,
    RoutingRuleCreate, RoutingRuleResponse,
)

router = APIRouter()

@router.post("/scoring", response_model=ScoringRuleResponse, status_code=status.HTTP_201_CREATED)
def create_scoring_rule(
    tenant_id: UUID,
    request: ScoringRuleCreate,
    use_case: CreateScoringRuleInputPort = Depends(get_create_scoring_rule_use_case),
):
    command = CreateScoringRuleCommand(
        tenant_id=tenant_id,
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
    tenant_id: UUID,
    use_case: GetScoringRulesInputPort = Depends(get_get_scoring_rules_use_case),
):
    query = GetRulesQuery(tenant_id=tenant_id)
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

@router.post("/routing", response_model=RoutingRuleResponse, status_code=status.HTTP_201_CREATED)
def create_routing_rule(
    tenant_id: UUID,
    request: RoutingRuleCreate,
    use_case: CreateRoutingRuleInputPort = Depends(get_create_routing_rule_use_case),
):
    command = CreateRoutingRuleCommand(
        tenant_id=tenant_id,
        min_score=request.min_score,
        target_team=request.target_team,
        assignment_strategy=request.assignment_strategy,
        target_agent_ids=request.target_agent_ids,
    )
    saved = use_case.execute(command)
    return RoutingRuleResponse(
        id=str(saved.id),
        min_score=saved.min_score,
        target_team=saved.target_team,
        assignment_strategy=saved.assignment_strategy.value,
        target_agent_ids=[str(i) for i in saved.target_agent_ids],
    )

@router.get("/routing", response_model=List[RoutingRuleResponse], status_code=status.HTTP_200_OK)
def list_routing_rules(
    tenant_id: UUID,
    use_case: GetRoutingRulesInputPort = Depends(get_get_routing_rules_use_case),
):
    query = GetRulesQuery(tenant_id=tenant_id)
    rules = use_case.execute(query)
    return [
        RoutingRuleResponse(
            id=str(r.id),
            min_score=r.min_score,
            target_team=r.target_team,
            assignment_strategy=r.assignment_strategy.value,
            target_agent_ids=[str(i) for i in r.target_agent_ids],
        )
        for r in rules
    ]
