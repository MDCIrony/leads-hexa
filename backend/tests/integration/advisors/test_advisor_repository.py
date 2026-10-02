from uuid import uuid4

from domain.advisors.advisor import Advisor
from domain.entities.sales_group import SalesGroup
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.advisors.raw_sql_advisor_repository import RawSqlAdvisorRepository
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import RawSqlSalesGroupRepository


def _advisor(tenant, agent_id=None, name="Ana", role=AgentRole.AGENT, is_active=True, version=1) -> Advisor:
    return Advisor(AgentId(agent_id), TenantId(tenant), name, role, is_active, version)


def _group(conn, tenant):
    return RawSqlSalesGroupRepository(conn).save(SalesGroup.create(tenant_id=tenant, name=f"G {uuid4()}"))


def test_an_older_or_equal_version_does_not_overwrite_a_newer_one(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo, tenant, agent_id = RawSqlAdvisorRepository(conn), uuid4(), uuid4()
        repo.upsert_identity(_advisor(tenant, agent_id, name="Ana B.", version=3))

        repo.upsert_identity(_advisor(tenant, agent_id, name="Stale", is_active=False, version=2))
        repo.upsert_identity(_advisor(tenant, agent_id, name="Same", is_active=False, version=3))

        stored = repo.get(agent_id, tenant)
        assert (stored.name, stored.is_active, stored.version) == ("Ana B.", True, 3)


def test_an_identity_upsert_never_touches_the_group(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo, tenant, agent_id = RawSqlAdvisorRepository(conn), uuid4(), uuid4()
        group = _group(conn, tenant)
        repo.upsert_identity(_advisor(tenant, agent_id, version=1))
        assert repo.set_group(agent_id, tenant, group.id.value) is True

        repo.upsert_identity(_advisor(tenant, agent_id, name="Ana B.", version=2))

        stored = repo.get(agent_id, tenant)
        assert (stored.name, stored.version, stored.group_id.value) == ("Ana B.", 2, group.id.value)


def test_deleting_a_group_orphans_its_advisors(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo, tenant, agent_id = RawSqlAdvisorRepository(conn), uuid4(), uuid4()
        group = _group(conn, tenant)
        repo.upsert_identity(_advisor(tenant, agent_id))
        repo.set_group(agent_id, tenant, group.id.value)

        RawSqlSalesGroupRepository(conn).delete(group.id.value)

        assert repo.get(agent_id, tenant).group_id is None


def test_an_advisor_of_another_organization_reads_back_as_missing(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo, tenant, agent_id = RawSqlAdvisorRepository(conn), uuid4(), uuid4()
        repo.upsert_identity(_advisor(tenant, agent_id))

        assert repo.get(agent_id, uuid4()) is None
        assert repo.set_group(agent_id, uuid4(), None) is False


def test_available_advisors_are_the_active_people_ordered_by_name(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        repo, tenant = RawSqlAdvisorRepository(conn), uuid4()
        group = _group(conn, tenant)
        beto, ana = _advisor(tenant, name="Beto"), _advisor(tenant, name="Ana")
        for advisor in (beto, ana, _advisor(tenant, name="Off", is_active=False),
                        _advisor(tenant, name="Bot", role=AgentRole.INTEGRATION), _advisor(uuid4(), name="Elsewhere")):
            repo.upsert_identity(advisor)
        repo.set_group(beto.agent_id.value, tenant, group.id.value)

        assert [a.name for a in repo.list_available(tenant)] == ["Ana", "Beto"]
        assert [a.name for a in repo.list_available(tenant, group.id.value)] == ["Beto"]
        assert all(a.is_assignable for a in repo.list_available(tenant))
        assert [a.name for a in repo.list(tenant)] == ["Ana", "Beto", "Off"]
        assert [a.name for a in repo.list(tenant, is_active=False)] == ["Off"]
        assert [a.name for a in repo.list(tenant, limit=1, offset=1)] == ["Beto"]
        assert repo.count_by_group(tenant, group.id.value) == 1
