from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, status
from domain.entities.rule import ScoringRule, RoutingRule
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.input.api.dependencies import get_uow
from infrastructure.adapters.input.api.schemas import (
    ScoringRuleCreate,
    ScoringRuleResponse,
    RoutingRuleCreate,
    RoutingRuleResponse,
)

router = APIRouter()

@router.post("/scoring", response_model=ScoringRuleResponse, status_code=status.HTTP_201_CREATED)
def create_scoring_rule(
    tenant_id: UUID,
    request: ScoringRuleCreate,
    uow: UnitOfWorkPort = Depends(get_uow),
):
    rule = ScoringRule.create(
        name=request.name,
        field=request.field,
        operator=request.operator,
        value=request.value,
        score_delta=request.score_delta,
    )
    with uow:
        saved = uow.rules.save_scoring_rule(tenant_id, rule)
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
    uow: UnitOfWorkPort = Depends(get_uow),
):
    with uow:
        rules = uow.rules.get_scoring_rules_by_tenant(tenant_id)
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
    uow: UnitOfWorkPort = Depends(get_uow),
):
    rule = RoutingRule.create(
        min_score=request.min_score,
        target_team=request.target_team,
        assignment_strategy=request.assignment_strategy,
        target_agent_ids=request.target_agent_ids,
    )
    with uow:
        saved = uow.rules.save_routing_rule(tenant_id, rule)
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
    uow: UnitOfWorkPort = Depends(get_uow),
):
    with uow:
        rules = uow.rules.get_routing_rules_by_tenant(tenant_id)
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
