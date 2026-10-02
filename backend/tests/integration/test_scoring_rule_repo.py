from types import SimpleNamespace

import psycopg

from domain.value_objects.tenant_id import TenantId
from domain.entities.rule import ScoringRule
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import (
    RawSqlRuleRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlRuleRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> SimpleNamespace:
    # No row: since migration 017 nothing in leads_db references tenants.
    return SimpleNamespace(id=TenantId())


def test_lists_paginated_and_reads_back_by_id_scoped_to_tenant(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        other_tenant = _tenant(conn)
        low = ScoringRule.create(
            tenant_id=tenant.id.value, name="Baja", conditions=[], score_delta=5, priority=1
        )
        high = ScoringRule.create(
            tenant_id=tenant.id.value, name="Alta", conditions=[], score_delta=10, priority=9
        )
        repo.save_scoring_rule(tenant.id.value, low)
        repo.save_scoring_rule(tenant.id.value, high)

        page = repo.list_scoring_rules_by_tenant(tenant.id.value, limit=1, offset=0)
        assert [r.name for r in page] == ["Alta"]
        assert repo.count_scoring_rules_by_tenant(tenant.id.value) == 2

        found = repo.get_scoring_rule_by_id_and_tenant(high.id, tenant.id.value)
        assert found is not None
        assert found.name == "Alta"

        # A rule from another organization must read back as missing, never
        # confirmed to exist elsewhere.
        assert repo.get_scoring_rule_by_id_and_tenant(high.id, other_tenant.id.value) is None
    finally:
        ctx.__exit__(None, None, None)


def test_delete_removes_the_rule_scoped_to_tenant(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        rule = ScoringRule.create(
            tenant_id=tenant.id.value, name="Efímera", conditions=[], score_delta=5
        )
        repo.save_scoring_rule(tenant.id.value, rule)

        deleted = repo.delete_scoring_rule(rule.id, tenant.id.value)

        assert deleted is True
        assert repo.get_scoring_rule_by_id_and_tenant(rule.id, tenant.id.value) is None
    finally:
        ctx.__exit__(None, None, None)
