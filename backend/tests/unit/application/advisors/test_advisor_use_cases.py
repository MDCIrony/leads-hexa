import uuid

import pytest

from application.dtos.advisors import ListAdvisorsQuery, SetAdvisorGroupCommand
from application.use_cases.advisors.advisor_use_cases import ListAdvisorsUseCase, SetAdvisorGroupUseCase
from domain.advisors.advisor import Advisor
from domain.leads.lead import Lead
from domain.groups.sales_group import SalesGroup
from domain.exceptions import DomainException
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole, LeadStatus
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId
from tests.unit.mocks.advisors.in_memory_advisor_repo import ProjectionOnlyDirectory
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT = uuid.uuid4()


def _seed(uow, name, tenant=_TENANT, is_active=True, group=None, role=AgentRole.AGENT) -> Advisor:
    return uow.advisors.seed(Advisor(AgentId(), TenantId(tenant), name, role, is_active, 1,
                                     GroupId(group) if group else None))


def _assign(uow, advisor: Advisor) -> None:
    lead = Lead.create(tenant_id=_TENANT, source_id=uuid.uuid4(), first_name="L", last_name="X",
                       email=f"{uuid.uuid4().hex[:6]}@x.test", company="Acme", budget=1, industry="tech",
                       status=LeadStatus.UNASSIGNED)
    lead.assign_to(advisor.agent_id, advisor.tenant_id)
    uow.leads.save(lead)


def _group(uow, tenant=_TENANT) -> uuid.UUID:
    return uow.groups.save(SalesGroup.create(tenant_id=tenant, name=f"G {uuid.uuid4()}")).id.value


def test_the_list_carries_each_advisors_active_load_and_the_total():
    uow = InMemoryUnitOfWork()
    ana, bea = _seed(uow, "Ana"), _seed(uow, "Bea")
    _seed(uow, "Other org", tenant=uuid.uuid4())
    _seed(uow, "Machine", role=AgentRole.INTEGRATION)
    _assign(uow, ana)
    _assign(uow, ana)

    page = ListAdvisorsUseCase(uow).execute(ListAdvisorsQuery(_TENANT, limit=1))

    assert page.total == 2
    assert [(v.advisor.name, v.active_load) for v in page.items] == [("Ana", 2)]
    second = ListAdvisorsUseCase(uow).execute(ListAdvisorsQuery(_TENANT, limit=1, offset=1))
    assert [(v.advisor.agent_id, v.active_load) for v in second.items] == [(bea.agent_id, 0)]


def test_the_list_filters_by_group_and_activity():
    uow = InMemoryUnitOfWork()
    group = _group(uow)
    _seed(uow, "Ana", group=group)
    _seed(uow, "Bea", group=group, is_active=False)
    _seed(uow, "Cris")

    names = lambda **f: [v.advisor.name for v in ListAdvisorsUseCase(uow).execute(
        ListAdvisorsQuery(_TENANT, **f)).items]

    assert names(group_id=group) == ["Ana", "Bea"]
    assert names(group_id=group, is_active=False) == ["Bea"]
    assert names(is_active=True) == ["Ana", "Cris"]


def test_a_group_is_set_and_cleared():
    uow = InMemoryUnitOfWork()
    advisor, group = _seed(uow, "Ana"), _group(uow)
    use_case = SetAdvisorGroupUseCase(uow, ProjectionOnlyDirectory(uow))

    view = use_case.execute(SetAdvisorGroupCommand(_TENANT, advisor.agent_id.value, group))
    assert view.advisor.group_id.value == group and view.active_load == 0

    cleared = use_case.execute(SetAdvisorGroupCommand(_TENANT, advisor.agent_id.value, None))
    assert cleared.advisor.group_id is None


@pytest.mark.parametrize("group_of", [lambda uow: _group(uow, tenant=uuid.uuid4()), lambda uow: uuid.uuid4()],
                         ids=["other-organization", "missing"])
def test_a_group_that_is_not_the_organizations_is_not_found(group_of):
    uow = InMemoryUnitOfWork()
    advisor = _seed(uow, "Ana")

    with pytest.raises(DomainException) as exc:
        SetAdvisorGroupUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
            SetAdvisorGroupCommand(_TENANT, advisor.agent_id.value, group_of(uow)))
    assert exc.value.error_code == "GROUP_NOT_FOUND"
    assert uow.advisors.get(advisor.agent_id.value, _TENANT).group_id is None


def test_the_agent_is_resolved_through_the_directory():
    uow = InMemoryUnitOfWork()
    foreign = _seed(uow, "Ana", tenant=uuid.uuid4())

    with pytest.raises(DomainException) as exc:
        SetAdvisorGroupUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
            SetAdvisorGroupCommand(_TENANT, foreign.agent_id.value, None))
    assert exc.value.error_code == "AGENT_NOT_FOUND"


def test_an_advisor_gone_between_resolution_and_update_is_not_found():
    uow = InMemoryUnitOfWork()
    advisor = _seed(uow, "Ana")

    class _Resolves:
        def get(self, agent_id, tenant_id):
            uow.advisors.advisors.pop(agent_id)
            return advisor

    with pytest.raises(DomainException) as exc:
        SetAdvisorGroupUseCase(uow, _Resolves()).execute(SetAdvisorGroupCommand(_TENANT, advisor.agent_id.value, None))
    assert exc.value.error_code == "AGENT_NOT_FOUND"
