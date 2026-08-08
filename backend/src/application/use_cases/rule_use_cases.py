from typing import List
from uuid import UUID

from application.dtos.commands import (
    CreateAssignmentRuleCommand,
    CreateScoringRuleCommand,
    UpdateAssignmentRuleCommand,
)
from application.dtos.queries import GetAssignmentRulesQuery, GetRulesQuery
from application.ports.input.rule_use_case_ports import (
    CreateAssignmentRuleInputPort,
    CreateScoringRuleInputPort,
    DeleteAssignmentRuleInputPort,
    GetAssignmentRulesInputPort,
    GetScoringRulesInputPort,
    UpdateAssignmentRuleInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.rule import AssignmentRule, ScoringRule
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy


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
            tenant_id=command.tenant_id,
            name=command.name,
            conditions=command.conditions,
            score_delta=command.score_delta,
            priority=command.priority,
            is_active=command.is_active,
        )
        with self.uow:
            return self.uow.rules.save_scoring_rule(command.tenant_id, rule)


def _get_owned_rule(uow: UnitOfWorkPort, tenant_id: UUID, rule_id: UUID) -> AssignmentRule:
    """Looked up through the tenant's own rules rather than a bare get-by-id,
    so a foreign rule reads back as missing instead of a 403 that would
    confirm it exists in someone else's organization."""
    rules = uow.rules.get_assignment_rules_by_tenant(tenant_id)
    rule = next((r for r in rules if r.id == rule_id), None)
    if rule is None:
        raise DomainException("La regla no existe", error_code="ASSIGNMENT_RULE_NOT_FOUND")
    return rule


class CreateAssignmentRuleUseCase(CreateAssignmentRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: CreateAssignmentRuleCommand) -> AssignmentRule:
        rule = AssignmentRule.create(
            tenant_id=command.tenant_id,
            name=command.name,
            min_score=command.min_score,
            max_score=command.max_score,
            target_group_id=command.target_group_id,
            target_agent_ids=command.target_agent_ids,
            agent_match_mode=command.agent_match_mode,
            strategy=command.strategy,
            priority=command.priority,
        )
        with self.uow:
            return self.uow.rules.save_assignment_rule(command.tenant_id, rule)


class GetAssignmentRulesUseCase(GetAssignmentRulesInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAssignmentRulesQuery) -> List[AssignmentRule]:
        with self.uow:
            return self.uow.rules.get_assignment_rules_by_tenant(query.tenant_id)


class UpdateAssignmentRuleUseCase(UpdateAssignmentRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: UpdateAssignmentRuleCommand) -> AssignmentRule:
        with self.uow:
            rule = _get_owned_rule(self.uow, command.tenant_id, command.rule_id)
            if command.name is not None:
                rule.name = command.name.strip()
            if command.min_score is not None:
                rule.min_score = command.min_score
            if command.max_score is not None:
                rule.max_score = command.max_score
            if command.target_group_id is not None:
                rule.target_group_id = command.target_group_id
            if command.target_agent_ids is not None:
                rule.target_agent_ids = list(command.target_agent_ids)
            if command.agent_match_mode is not None:
                rule.agent_match_mode = AgentMatchMode(command.agent_match_mode)
            if command.strategy is not None:
                rule.strategy = AssignmentStrategy(command.strategy)
            if command.priority is not None:
                rule.priority = command.priority
            if command.is_active is not None:
                rule.is_active = command.is_active
            # rr_cursor is never a command field, so a partial update leaves
            # an in-progress rotation exactly where it was.
            return self.uow.rules.save_assignment_rule(command.tenant_id, rule)


class DeleteAssignmentRuleUseCase(DeleteAssignmentRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, tenant_id: UUID, rule_id: UUID) -> None:
        with self.uow:
            _get_owned_rule(self.uow, tenant_id, rule_id)
            self.uow.rules.delete_assignment_rule(rule_id)
