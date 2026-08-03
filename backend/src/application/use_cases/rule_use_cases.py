from typing import List
from application.dtos.queries import GetRulesQuery
from application.dtos.commands import CreateScoringRuleCommand, CreateRoutingRuleCommand
from application.ports.input.rule_use_case_ports import (
    GetScoringRulesInputPort, CreateScoringRuleInputPort,
    GetRoutingRulesInputPort, CreateRoutingRuleInputPort
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.rule import ScoringRule, RoutingRule
from domain.value_objects.enums import Operator, AssignmentStrategy

class GetScoringRulesUseCase(GetScoringRulesInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetRulesQuery) -> List[ScoringRule]:
        with self.uow:
            return self.uow.rules.get_scoring_rules_by_tenant(query.tenant_id)

class CreateScoringRuleUseCase(CreateScoringRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: CreateScoringRuleCommand) -> ScoringRule:
        rule = ScoringRule.create(
            name=command.name,
            field=command.field,
            operator=Operator(command.operator),
            value=command.value,
            score_delta=command.score_delta
        )
        with self.uow:
            return self.uow.rules.save_scoring_rule(command.tenant_id, rule)

class GetRoutingRulesUseCase(GetRoutingRulesInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetRulesQuery) -> List[RoutingRule]:
        with self.uow:
            return self.uow.rules.get_routing_rules_by_tenant(query.tenant_id)

class CreateRoutingRuleUseCase(CreateRoutingRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: CreateRoutingRuleCommand) -> RoutingRule:
        rule = RoutingRule.create(
            min_score=command.min_score,
            target_team=command.target_team,
            assignment_strategy=AssignmentStrategy(command.assignment_strategy),
            target_agent_ids=command.target_agent_ids
        )
        with self.uow:
            return self.uow.rules.save_routing_rule(command.tenant_id, rule)
