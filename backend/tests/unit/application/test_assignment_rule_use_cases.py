import uuid

import pytest

from application.dtos.commands import CreateAssignmentRuleCommand, UpdateAssignmentRuleCommand
from application.dtos.queries import GetAssignmentRulesQuery
from application.use_cases.rule_use_cases import (
    CreateAssignmentRuleUseCase,
    DeleteAssignmentRuleUseCase,
    GetAssignmentRulesUseCase,
    UpdateAssignmentRuleUseCase,
)
from domain.exceptions import DomainException
from tests.unit.mocks.in_memory_advisor_repo import make_advisor
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        groups=InMemorySalesGroupRepository(),
    )


class TestCreateAssignmentRule:
    def test_creates_a_rule_with_a_band_and_a_priority(self):
        uow = _uow()
        tenant = uuid.uuid4()
        target = uuid.uuid4()

        rule = CreateAssignmentRuleUseCase(uow=uow).execute(
            CreateAssignmentRuleCommand(
                tenant_id=tenant,
                name="Alta",
                min_score=70,
                max_score=100,
                target_agent_ids=[target],
                priority=10,
            )
        )

        assert rule.min_score == 70
        assert rule.max_score == 100
        assert rule.priority == 10
        assert rule.target_agent_ids == [target]


class TestUpdateAssignmentRule:
    def test_a_partial_update_preserves_the_rotation_cursor(self):
        uow = _uow()
        tenant = uuid.uuid4()
        target = uuid.uuid4()
        rule = CreateAssignmentRuleUseCase(uow=uow).execute(
            CreateAssignmentRuleCommand(tenant_id=tenant, name="R", target_agent_ids=[target])
        )
        # Simulate rotations that already happened before this update.
        rule.rr_cursor = 7
        uow.rules.save_assignment_rule(tenant, rule)

        updated = UpdateAssignmentRuleUseCase(uow=uow).execute(
            UpdateAssignmentRuleCommand(tenant_id=tenant, rule_id=rule.id, name="R renombrada")
        )

        assert updated.name == "R renombrada"
        assert updated.rr_cursor == 7

    def test_updating_a_rule_of_another_organization_is_rejected(self):
        uow = _uow()
        tenant, other = uuid.uuid4(), uuid.uuid4()
        target = uuid.uuid4()
        rule = CreateAssignmentRuleUseCase(uow=uow).execute(
            CreateAssignmentRuleCommand(tenant_id=tenant, name="R", target_agent_ids=[target])
        )

        with pytest.raises(DomainException) as exc:
            UpdateAssignmentRuleUseCase(uow=uow).execute(
                UpdateAssignmentRuleCommand(tenant_id=other, rule_id=rule.id, name="Hijack")
            )
        assert exc.value.error_code == "ASSIGNMENT_RULE_NOT_FOUND"


class TestDeleteAssignmentRule:
    def test_deleting_a_rule_does_not_touch_its_agents(self):
        uow = _uow()
        tenant = uuid.uuid4()
        agent = uow.advisors.seed(make_advisor(name="Ana", tenant_id=tenant))
        rule = CreateAssignmentRuleUseCase(uow=uow).execute(
            CreateAssignmentRuleCommand(
                tenant_id=tenant, name="R", target_agent_ids=[agent.id.value]
            )
        )

        DeleteAssignmentRuleUseCase(uow=uow).execute(tenant_id=tenant, rule_id=rule.id)

        assert uow.rules.get_assignment_rules_by_tenant(tenant) == []
        survivor = uow.advisors.get_any(agent.id.value)
        assert survivor is not None
        assert survivor.is_active is True


class TestGetAssignmentRules:
    def test_lists_rules_ordered_by_descending_priority(self):
        uow = _uow()
        tenant = uuid.uuid4()
        target = uuid.uuid4()
        low = CreateAssignmentRuleUseCase(uow=uow).execute(
            CreateAssignmentRuleCommand(
                tenant_id=tenant, name="Baja", target_agent_ids=[target], priority=1
            )
        )
        high = CreateAssignmentRuleUseCase(uow=uow).execute(
            CreateAssignmentRuleCommand(
                tenant_id=tenant, name="Alta", target_agent_ids=[target], priority=9
            )
        )

        rules = GetAssignmentRulesUseCase(uow=uow).execute(GetAssignmentRulesQuery(tenant_id=tenant))

        assert [r.id for r in rules] == [high.id, low.id]
