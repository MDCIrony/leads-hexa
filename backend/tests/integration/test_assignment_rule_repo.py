from types import SimpleNamespace
from uuid import uuid4

import psycopg

from domain.value_objects.tenant_id import TenantId
from domain.rules.assignment_rule import AssignmentRule
from domain.groups.sales_group import SalesGroup
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import (
    RawSqlRuleRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import (
    RawSqlSalesGroupRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlRuleRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> SimpleNamespace:
    # No row: since migration 017 nothing in leads_db references tenants.
    return SimpleNamespace(id=TenantId())


def test_saves_and_reads_back_every_field(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        group = RawSqlSalesGroupRepository(conn).save(
            SalesGroup.create(tenant_id=tenant.id.value, name="Ventas")
        )
        agent_id = uuid4()
        rule = AssignmentRule.create(
            tenant_id=tenant.id.value,
            name="Regla principal",
            min_score=20,
            max_score=80,
            target_group_id=group.id.value,
            target_agent_ids=[agent_id],
            agent_match_mode=AgentMatchMode.ONLY,
            strategy=AssignmentStrategy.ROUND_ROBIN,
            priority=5,
        )

        repo.save_assignment_rule(tenant.id.value, rule)

        [found] = repo.get_assignment_rules_by_tenant(tenant.id.value)
        assert found.id == rule.id
        assert found.name == "Regla principal"
        assert found.min_score == 20
        assert found.max_score == 80
        assert found.target_group_id == group.id.value
        assert found.target_agent_ids == [agent_id]
        assert found.agent_match_mode == AgentMatchMode.ONLY
        assert found.strategy == AssignmentStrategy.ROUND_ROBIN
        assert found.priority == 5
        assert found.is_active is True
        assert found.rr_cursor == 0
    finally:
        ctx.__exit__(None, None, None)


def test_listing_is_scoped_to_the_organization_and_ordered_by_priority(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant_a = _tenant(conn)
        tenant_b = _tenant(conn)
        low = AssignmentRule.create(
            tenant_id=tenant_a.id.value, name="Baja", target_agent_ids=[uuid4()], priority=1
        )
        high = AssignmentRule.create(
            tenant_id=tenant_a.id.value, name="Alta", target_agent_ids=[uuid4()], priority=9
        )
        other = AssignmentRule.create(
            tenant_id=tenant_b.id.value, name="Otra organización", target_agent_ids=[uuid4()]
        )
        repo.save_assignment_rule(tenant_a.id.value, low)
        repo.save_assignment_rule(tenant_a.id.value, high)
        repo.save_assignment_rule(tenant_b.id.value, other)

        found = repo.get_assignment_rules_by_tenant(tenant_a.id.value)

        assert [r.name for r in found] == ["Alta", "Baja"]
    finally:
        ctx.__exit__(None, None, None)


def test_saving_persists_the_rotation_cursor(test_db):
    """The core guarantee of this task: skip this and round-robin resets to
    the start on every request instead of rotating, because a fresh
    AssignmentEngine has no memory of its own."""
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        rule = AssignmentRule.create(
            tenant_id=tenant.id.value,
            name="Rotativa",
            target_agent_ids=[uuid4()],
            strategy=AssignmentStrategy.ROUND_ROBIN,
        )
        repo.save_assignment_rule(tenant.id.value, rule)

        rule.advance_cursor(3)
        rule.advance_cursor(3)
        repo.save_assignment_rule(tenant.id.value, rule)

        [found] = repo.get_assignment_rules_by_tenant(tenant.id.value)
        assert found.rr_cursor == 2
    finally:
        ctx.__exit__(None, None, None)


def test_delete_removes_the_rule(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        rule = AssignmentRule.create(
            tenant_id=tenant.id.value, name="Efímera", target_agent_ids=[uuid4()]
        )
        repo.save_assignment_rule(tenant.id.value, rule)

        repo.delete_assignment_rule(rule.id)

        assert repo.get_assignment_rules_by_tenant(tenant.id.value) == []
    finally:
        ctx.__exit__(None, None, None)
