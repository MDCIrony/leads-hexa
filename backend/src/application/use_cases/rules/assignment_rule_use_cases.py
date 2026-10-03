from typing import List
from uuid import UUID

from application.dtos.rules import (
    CreateAssignmentRuleCommand,
    GetAssignmentRulesQuery,
    UpdateAssignmentRuleCommand,
)
from application.ports.input.rules.rule_use_case_ports import (
    CreateAssignmentRuleInputPort,
    DeleteAssignmentRuleInputPort,
    GetAssignmentRulesInputPort,
    UpdateAssignmentRuleInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import DomainException
from domain.rules.assignment_rule import AssignmentRule
from domain.value_objects.criterion import Criterion
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy


def _get_owned_rule(uow: UnitOfWorkPort, tenant_id: UUID, rule_id: UUID) -> AssignmentRule:
    """Looked up through the tenant's own rules rather than a bare get-by-id,
    so a foreign rule reads back as missing instead of a 403 that would
    confirm it exists in someone else's organization."""
    rules = uow.rules.get_assignment_rules_by_tenant(tenant_id)
    rule = next((r for r in rules if r.id == rule_id), None)
    if rule is None:
        raise DomainException("La regla no existe", error_code="ASSIGNMENT_RULE_NOT_FOUND")
    return rule


def _ensure_group_exists(uow: UnitOfWorkPort, tenant_id: UUID, group_id: UUID) -> None:
    """Scoped to the tenant so a foreign-key violation on an unknown group
    never escapes as a 500, and a group from another organization reads
    back as missing rather than silently accepted."""
    group = uow.groups.get_by_id(group_id)
    if group is None or str(group.tenant_id) != str(tenant_id):
        raise DomainException("El grupo no existe", error_code="GROUP_NOT_FOUND")


class CreateAssignmentRuleUseCase(CreateAssignmentRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: CreateAssignmentRuleCommand) -> AssignmentRule:
        with self.uow:
            if command.target_group_id is not None:
                _ensure_group_exists(self.uow, command.tenant_id, command.target_group_id)
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
                conditions=command.conditions,
            )
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
                _ensure_group_exists(self.uow, command.tenant_id, command.target_group_id)
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
            if command.conditions is not None:
                rule.conditions = [Criterion.from_dict(c) for c in command.conditions]
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
