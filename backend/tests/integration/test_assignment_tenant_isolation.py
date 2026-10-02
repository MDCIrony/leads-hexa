import uuid

from domain.advisors.advisor import Advisor
from domain.groups.sales_group import SalesGroup
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.advisors.raw_sql_advisor_repository import (
    RawSqlAdvisorRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import (
    RawSqlSalesGroupRepository,
)

_TENANT_A = uuid.uuid4()
_TENANT_B = uuid.uuid4()


def _seed(repo: RawSqlAdvisorRepository, name: str, tenant_id: uuid.UUID, group_id=None) -> Advisor:
    advisor = Advisor(AgentId(), TenantId(tenant_id), name, AgentRole.AGENT, True, 1)
    repo.upsert_identity(advisor)
    if group_id:
        repo.set_group(advisor.agent_id.value, tenant_id, group_id)
    return advisor


def test_available_agents_never_cross_organizations(test_db):
    """A lead of one organization must never reach another's sales agents.

    Before the fix the candidate pool was filtered by team name alone, so two
    organizations both calling their team "Sales" shared candidates."""
    with test_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAdvisorRepository(conn)
        _seed(repo, "Ana", _TENANT_A)
        _seed(repo, "Bruno", _TENANT_B)

        found = repo.list_available(_TENANT_A)

        assert [a.name for a in found] == ["Ana"]


def test_available_agents_still_filter_by_group(test_db):
    """The group filter narrows the pool without ever widening it past the
    organization: group_id is a real foreign key now, not a free string."""
    with test_db.get_connection(autocommit=True) as conn:
        tenant = uuid.uuid4()
        group_repo = RawSqlSalesGroupRepository(conn)
        sales = group_repo.save(SalesGroup.create(tenant_id=tenant, name="Sales"))
        support = group_repo.save(SalesGroup.create(tenant_id=tenant, name="Support"))

        repo = RawSqlAdvisorRepository(conn)
        _seed(repo, "Ana", tenant, sales.id.value)
        _seed(repo, "Carla", tenant, support.id.value)

        assert len(repo.list_available(tenant, group_id=sales.id.value)) == 1
        assert len(repo.list_available(tenant)) == 2


def test_a_group_of_another_organization_yields_no_candidates(test_db):
    """The organization filter wins over the group filter. Without it, knowing
    a group id would be enough to reach that group's agents from outside."""
    with test_db.get_connection(autocommit=True) as conn:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        group_repo = RawSqlSalesGroupRepository(conn)
        # Both organizations name their group "Sales" — the collision that made
        # the original leak invisible.
        group_a = group_repo.save(SalesGroup.create(tenant_id=tenant_a, name="Sales"))
        group_repo.save(SalesGroup.create(tenant_id=tenant_b, name="Sales"))

        repo = RawSqlAdvisorRepository(conn)
        _seed(repo, "Ana", tenant_a, group_a.id.value)

        assert repo.list_available(tenant_b, group_id=group_a.id.value) == []
