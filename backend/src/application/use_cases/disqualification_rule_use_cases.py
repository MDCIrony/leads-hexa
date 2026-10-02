from uuid import UUID

from application.dtos.commands import (
    CreateDisqualificationRuleCommand,
    DisqualificationRulesPageResult,
    UpdateDisqualificationRuleCommand,
)
from application.dtos.queries import GetDisqualificationRulesQuery
from application.ports.input.disqualification_rule_use_case_ports import (
    CreateDisqualificationRuleInputPort,
    DeleteDisqualificationRuleInputPort,
    GetDisqualificationRulesInputPort,
    UpdateDisqualificationRuleInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.rules.disqualification_rule import DisqualificationRule
from domain.exceptions import DomainException


def _get_owned_rule(uow: UnitOfWorkPort, tenant_id: UUID, rule_id: UUID) -> DisqualificationRule:
    """A rule from another organization must read back as missing, never as
    a 403 that would confirm it exists elsewhere."""
    rule = uow.disqualification_rules.get_by_id_and_tenant(rule_id, tenant_id)
    if rule is None:
        raise DomainException(
            "La regla no existe",
            error_code="DISQUALIFICATION_RULE_NOT_FOUND",
        )
    return rule


class CreateDisqualificationRuleUseCase(CreateDisqualificationRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: CreateDisqualificationRuleCommand) -> DisqualificationRule:
        with self.uow:
            rule = DisqualificationRule.create(
                tenant_id=command.tenant_id,
                name=command.name,
                conditions=command.conditions,
                priority=command.priority,
                is_active=command.is_active,
            )
            return self.uow.disqualification_rules.save(rule)


class GetDisqualificationRulesUseCase(GetDisqualificationRulesInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetDisqualificationRulesQuery) -> DisqualificationRulesPageResult:
        with self.uow:
            items = self.uow.disqualification_rules.list_by_tenant(
                query.tenant_id, limit=query.limit, offset=query.offset
            )
            total = self.uow.disqualification_rules.count_by_tenant(query.tenant_id)
        return DisqualificationRulesPageResult(items=items, total=total)


class UpdateDisqualificationRuleUseCase(UpdateDisqualificationRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: UpdateDisqualificationRuleCommand) -> DisqualificationRule:
        with self.uow:
            rule = _get_owned_rule(self.uow, command.tenant_id, command.rule_id)
            # This entity has no field-level setters, so a
            # PATCH goes back through create(): that is what stops it from
            # producing a rule create() itself would refuse, e.g. an emptied
            # name or an emptied condition list (R3).
            updated = DisqualificationRule.create(
                tenant_id=rule.tenant_id,
                name=command.name if command.name is not None else rule.name,
                conditions=command.conditions if command.conditions is not None else rule.conditions,
                priority=command.priority if command.priority is not None else rule.priority,
                is_active=command.is_active if command.is_active is not None else rule.is_active,
                rule_id=rule.id,
            )
            return self.uow.disqualification_rules.save(updated)


class DeleteDisqualificationRuleUseCase(DeleteDisqualificationRuleInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID, rule_id: UUID) -> None:
        with self.uow:
            _get_owned_rule(self.uow, tenant_id, rule_id)
            self.uow.disqualification_rules.delete(rule_id, tenant_id)
