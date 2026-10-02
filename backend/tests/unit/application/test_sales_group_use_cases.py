import uuid

import pytest

from application.dtos.commands import CreateSalesGroupCommand, UpdateSalesGroupCommand
from application.dtos.queries import GetSalesGroupsQuery
from application.use_cases.sales_group_use_cases import (
    CreateSalesGroupUseCase,
    DeleteSalesGroupUseCase,
    GetSalesGroupsUseCase,
    UpdateSalesGroupUseCase,
)
from domain.advisors.advisor import Advisor
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId
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


def _advisor(tenant_id: uuid.UUID, group_id, is_active: bool = True) -> Advisor:
    return Advisor(AgentId(), TenantId(tenant_id), "Ana", AgentRole.AGENT, is_active, 1,
                   GroupId(group_id) if group_id else None)


def _command(tenant_id: uuid.UUID, name: str = "Ventas Norte") -> CreateSalesGroupCommand:
    return CreateSalesGroupCommand(tenant_id=tenant_id, name=name)


class TestCreateSalesGroup:
    def test_a_new_group_is_listed_in_its_own_organization(self):
        uow = _uow()
        tenant = uuid.uuid4()
        CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))

        page = GetSalesGroupsUseCase(uow=uow).execute(GetSalesGroupsQuery(tenant_id=tenant))
        assert page.total == 1
        assert page.items[0].group.name == "Ventas Norte"

    def test_a_new_group_does_not_appear_in_another_organization(self):
        uow = _uow()
        tenant, other = uuid.uuid4(), uuid.uuid4()
        CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))

        page = GetSalesGroupsUseCase(uow=uow).execute(GetSalesGroupsQuery(tenant_id=other))
        assert page.total == 0

    def test_a_duplicate_name_in_the_same_organization_is_rejected(self):
        uow = _uow()
        tenant = uuid.uuid4()
        use_case = CreateSalesGroupUseCase(uow=uow)
        use_case.execute(_command(tenant))

        with pytest.raises(DomainException) as exc:
            use_case.execute(_command(tenant))
        assert exc.value.error_code == "GROUP_ALREADY_EXISTS"

    def test_the_same_name_is_accepted_in_a_different_organization(self):
        uow = _uow()
        tenant, other = uuid.uuid4(), uuid.uuid4()
        use_case = CreateSalesGroupUseCase(uow=uow)
        use_case.execute(_command(tenant))

        group = use_case.execute(_command(other))
        assert group.name == "Ventas Norte"


class TestUpdateSalesGroup:
    def test_renaming_changes_the_name_and_keeps_the_identifier(self):
        uow = _uow()
        tenant = uuid.uuid4()
        group = CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))

        updated = UpdateSalesGroupUseCase(uow=uow).execute(
            UpdateSalesGroupCommand(tenant_id=tenant, group_id=group.id.value, name="Ventas Sur")
        )

        assert updated.name == "Ventas Sur"
        assert updated.id.value == group.id.value

    def test_deactivating_a_group_does_not_deactivate_its_agents(self):
        """Unlike deactivating an organization, this only stops new automatic
        assignments: agents already in the group keep working the leads they
        already have."""
        uow = _uow()
        tenant = uuid.uuid4()
        group = CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))
        agent = uow.advisors.seed(
            make_advisor(
                name="Ana", group_id=group.id.value, tenant_id=tenant
            )
        )

        UpdateSalesGroupUseCase(uow=uow).execute(
            UpdateSalesGroupCommand(tenant_id=tenant, group_id=group.id.value, is_active=False)
        )

        assert uow.groups.get_by_id(group.id.value).is_active is False
        assert uow.advisors.get_any(agent.id.value).is_active is True

    def test_updating_a_group_of_another_organization_is_rejected(self):
        uow = _uow()
        tenant, other = uuid.uuid4(), uuid.uuid4()
        group = CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))

        with pytest.raises(DomainException) as exc:
            UpdateSalesGroupUseCase(uow=uow).execute(
                UpdateSalesGroupCommand(tenant_id=other, group_id=group.id.value, name="Hijack")
            )
        assert exc.value.error_code == "GROUP_NOT_FOUND"


class TestDeleteSalesGroup:
    def test_deleting_a_group_leaves_its_advisors_without_a_group(self):
        uow = _uow()
        tenant = uuid.uuid4()
        group = CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))
        advisor = uow.advisors.seed(_advisor(tenant, group.id.value))

        DeleteSalesGroupUseCase(uow=uow).execute(tenant_id=tenant, group_id=group.id.value)

        assert uow.groups.get_by_id(group.id.value) is None
        survivor = uow.advisors.get(advisor.agent_id.value, tenant)
        assert survivor is not None
        assert survivor.group_id is None


def test_deleting_a_group_records_no_agent_event():
    """group_id is lead-core's, not identity data: orphaning an advisor is no agent write."""
    uow = _uow()
    tenant = uuid.uuid4()
    group = CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))
    uow.advisors.seed(_advisor(tenant, group.id.value))

    DeleteSalesGroupUseCase(uow=uow).execute(tenant_id=tenant, group_id=group.id.value)

    assert uow.outbox.list_unpublished("internal", 10) == []


def test_the_listing_counts_the_active_advisors_of_each_group():
    uow = _uow()
    tenant = uuid.uuid4()
    group = CreateSalesGroupUseCase(uow=uow).execute(_command(tenant))
    uow.advisors.seed(_advisor(tenant, group.id.value))
    uow.advisors.seed(_advisor(tenant, group.id.value, is_active=False))
    uow.advisors.seed(_advisor(tenant, None))

    page = GetSalesGroupsUseCase(uow=uow).execute(GetSalesGroupsQuery(tenant_id=tenant))

    assert [item.agent_count for item in page.items] == [1]
