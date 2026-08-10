import uuid

import pytest

from application.dtos.commands import CreateScoringRuleCommand, UpdateScoringRuleCommand
from application.dtos.queries import GetRulesQuery
from application.use_cases.rule_use_cases import (
    CreateScoringRuleUseCase,
    DeleteScoringRuleUseCase,
    GetScoringRulesUseCase,
    UpdateScoringRuleUseCase,
)
from domain.exceptions import DomainException
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(rules=InMemoryRuleRepository())


class TestGetScoringRules:
    def test_returns_a_page_scoped_to_the_organization(self):
        uow = _uow()
        tenant = uuid.uuid4()
        other_tenant = uuid.uuid4()
        CreateScoringRuleUseCase(uow=uow).execute(
            CreateScoringRuleCommand(tenant_id=tenant, name="R1", conditions=[], score_delta=5)
        )
        CreateScoringRuleUseCase(uow=uow).execute(
            CreateScoringRuleCommand(tenant_id=other_tenant, name="R2", conditions=[], score_delta=5)
        )

        page = GetScoringRulesUseCase(uow=uow).execute(GetRulesQuery(tenant_id=tenant))

        assert page.total == 1
        assert [r.name for r in page.items] == ["R1"]


class TestUpdateScoringRule:
    def test_a_partial_update_preserves_the_conditions(self):
        uow = _uow()
        tenant = uuid.uuid4()
        rule = CreateScoringRuleUseCase(uow=uow).execute(
            CreateScoringRuleCommand(
                tenant_id=tenant,
                name="R",
                conditions=[{"field": "budget", "operator": "GREATER_THAN", "value": 100}],
                score_delta=5,
            )
        )

        updated = UpdateScoringRuleUseCase(uow=uow).execute(
            UpdateScoringRuleCommand(tenant_id=tenant, rule_id=rule.id, is_active=False)
        )

        assert updated.is_active is False
        assert len(updated.conditions) == 1
        assert updated.name == "R"
        assert updated.score_delta == 5

    def test_a_rule_from_another_organization_reads_back_as_missing(self):
        uow = _uow()
        tenant = uuid.uuid4()
        other_tenant = uuid.uuid4()
        rule = CreateScoringRuleUseCase(uow=uow).execute(
            CreateScoringRuleCommand(tenant_id=tenant, name="R", conditions=[], score_delta=5)
        )

        with pytest.raises(DomainException) as exc_info:
            UpdateScoringRuleUseCase(uow=uow).execute(
                UpdateScoringRuleCommand(tenant_id=other_tenant, rule_id=rule.id, is_active=False)
            )

        assert exc_info.value.error_code == "SCORING_RULE_NOT_FOUND"


class TestDeleteScoringRule:
    def test_deletes_the_rule(self):
        uow = _uow()
        tenant = uuid.uuid4()
        rule = CreateScoringRuleUseCase(uow=uow).execute(
            CreateScoringRuleCommand(tenant_id=tenant, name="R", conditions=[], score_delta=5)
        )

        DeleteScoringRuleUseCase(uow=uow).execute(tenant_id=tenant, rule_id=rule.id)

        page = GetScoringRulesUseCase(uow=uow).execute(GetRulesQuery(tenant_id=tenant))
        assert page.total == 0

    def test_a_rule_from_another_organization_reads_back_as_missing(self):
        uow = _uow()
        tenant = uuid.uuid4()
        other_tenant = uuid.uuid4()
        rule = CreateScoringRuleUseCase(uow=uow).execute(
            CreateScoringRuleCommand(tenant_id=tenant, name="R", conditions=[], score_delta=5)
        )

        with pytest.raises(DomainException) as exc_info:
            DeleteScoringRuleUseCase(uow=uow).execute(tenant_id=other_tenant, rule_id=rule.id)

        assert exc_info.value.error_code == "SCORING_RULE_NOT_FOUND"
