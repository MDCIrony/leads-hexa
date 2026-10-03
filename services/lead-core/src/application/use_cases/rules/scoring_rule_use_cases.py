from uuid import UUID

from application.dtos.rules import (
    CreateScoringRuleCommand,
    GetRulesQuery,
    ScoringRulesPageResult,
    UpdateScoringRuleCommand,
)
from application.ports.input.rules.rule_use_case_ports import (
    CreateScoringRuleInputPort,
    DeleteScoringRuleInputPort,
    GetScoringRulesInputPort,
    UpdateScoringRuleInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import DomainException
from domain.rules.scoring_rule import ScoringRule


def _get_owned_scoring_rule(uow: UnitOfWorkPort, tenant_id: UUID, rule_id: UUID) -> ScoringRule:
    """A rule from another organization must read back as missing, never as
    a 403 that would confirm it exists elsewhere."""
    rule = uow.rules.get_scoring_rule_by_id_and_tenant(rule_id, tenant_id)
    if rule is None:
        raise DomainException("La regla no existe", error_code="SCORING_RULE_NOT_FOUND")
    return rule


class GetScoringRulesUseCase(GetScoringRulesInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetRulesQuery) -> ScoringRulesPageResult:
        with self.uow:
            items = self.uow.rules.list_scoring_rules_by_tenant(
                query.tenant_id, limit=query.limit, offset=query.offset
            )
            total = self.uow.rules.count_scoring_rules_by_tenant(query.tenant_id)
        return ScoringRulesPageResult(items=items, total=total)


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


class UpdateScoringRuleUseCase(UpdateScoringRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: UpdateScoringRuleCommand) -> ScoringRule:
        with self.uow:
            rule = _get_owned_scoring_rule(self.uow, command.tenant_id, command.rule_id)
            # No field-level setters on this entity, so a PATCH goes back
            # through create(): that is what stops it from producing a rule
            # create() itself would refuse, e.g. an emptied name or an
            # emptied condition list. Copied from UpdateDisqualificationRuleUseCase.
            updated = ScoringRule.create(
                tenant_id=rule.tenant_id,
                name=command.name if command.name is not None else rule.name,
                conditions=command.conditions if command.conditions is not None else rule.conditions,
                score_delta=command.score_delta if command.score_delta is not None else rule.score_delta,
                priority=command.priority if command.priority is not None else rule.priority,
                is_active=command.is_active if command.is_active is not None else rule.is_active,
                rule_id=rule.id,
            )
            return self.uow.rules.save_scoring_rule(command.tenant_id, updated)


class DeleteScoringRuleUseCase(DeleteScoringRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, tenant_id: UUID, rule_id: UUID) -> None:
        with self.uow:
            _get_owned_scoring_rule(self.uow, tenant_id, rule_id)
            self.uow.rules.delete_scoring_rule(rule_id, tenant_id)
