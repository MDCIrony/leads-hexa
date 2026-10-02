from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from domain.rules.assignment_rule import AssignmentRule
from domain.groups.sales_group import SalesGroup
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.postgres_unit_of_work import (
    PostgresUnitOfWork,
)


def _tenant(test_db) -> SimpleNamespace:
    # No row: since migration 017 nothing in leads_db references tenants.
    return SimpleNamespace(id=TenantId())


def test_unique_violation_is_translated_to_already_exists(test_db):
    """A UniqueViolation raised inside the unit of work, bypassing any use
    case pre-check, must reach the caller as a DomainException — never as
    the raw psycopg error the exception_handlers module cannot recognize."""
    tenant = _tenant(test_db)
    uow = PostgresUnitOfWork(test_db)

    with pytest.raises(DomainException) as exc_info:
        with uow:
            uow.groups.save(SalesGroup.create(tenant_id=tenant.id.value, name="Dup"))
            uow.groups.save(SalesGroup.create(tenant_id=tenant.id.value, name="Dup"))

    assert exc_info.value.error_code == "ALREADY_EXISTS"
    assert not isinstance(exc_info.value, psycopg.errors.UniqueViolation)


def test_foreign_key_violation_is_translated_to_related_entity_not_found(test_db):
    """Same guarantee for a ForeignKeyViolation, e.g. an assignment rule
    pointing at a group id that does not exist."""
    tenant = _tenant(test_db)
    uow = PostgresUnitOfWork(test_db)

    rule = AssignmentRule.create(
        tenant_id=tenant.id.value,
        name="Regla huérfana",
        min_score=0,
        max_score=None,
        target_group_id=uuid4(),
        target_agent_ids=[],
        agent_match_mode=AgentMatchMode.ANY,
        strategy=AssignmentStrategy.ROUND_ROBIN,
        priority=10,
    )

    with pytest.raises(DomainException) as exc_info:
        with uow:
            uow.rules.save_assignment_rule(tenant.id.value, rule)

    assert exc_info.value.error_code == "RELATED_ENTITY_NOT_FOUND"
    assert not isinstance(exc_info.value, psycopg.errors.ForeignKeyViolation)


def test_not_null_violation_is_translated_to_missing_required_field(test_db):
    """A required column left empty must reach the caller as a 400-shaped
    domain error, not a 500. A message consumer reads a 500 as "retry me",
    and this one fails identically on every redelivery — it belongs in the
    dead-letter queue, not back in the queue."""
    tenant = _tenant(test_db)
    group = SalesGroup.create(tenant_id=tenant.id.value, name="A")
    uow = PostgresUnitOfWork(test_db)
    with uow:
        uow.groups.save(group)

    with pytest.raises(DomainException) as exc_info:
        with uow:
            uow.connection.execute(
                "UPDATE sales_groups SET name = NULL WHERE id = %s", (group.id.value,)
            )

    assert exc_info.value.error_code == "MISSING_REQUIRED_FIELD"
    assert not isinstance(exc_info.value, psycopg.errors.NotNullViolation)


def test_connection_returns_to_the_pool_after_a_translated_error(test_db):
    """A leaked connection only shows up under load; this is the cheapest
    signal that __exit__ still releases it back to the pool on the
    translation path."""
    tenant = _tenant(test_db)
    uow = PostgresUnitOfWork(test_db)

    with pytest.raises(DomainException):
        with uow:
            uow.groups.save(SalesGroup.create(tenant_id=tenant.id.value, name="Dup2"))
            uow.groups.save(SalesGroup.create(tenant_id=tenant.id.value, name="Dup2"))

    with uow:
        uow.groups.save(SalesGroup.create(tenant_id=tenant.id.value, name="Ok"))

    with test_db.get_connection(autocommit=True) as conn:
        row = conn.execute(
            "SELECT name FROM sales_groups WHERE tenant_id = %s", (tenant.id.value,)
        ).fetchall()
    assert {r["name"] for r in row} == {"Ok"}


def test_a_budget_beyond_the_column_is_a_domain_error_not_a_500(test_db):
    """Money accepts any finite non-negative amount, but leads.budget is
    NUMERIC(14, 2): a figure above 10^12 clears the domain and dies at the
    insert. Untranslated it left through the generic handler as a 500, which a
    client reads as "try again" for a value that overflows every time."""
    tenant = _tenant(test_db)
    uow = PostgresUnitOfWork(test_db)

    with pytest.raises(DomainException) as exc_info:
        with uow:
            uow.connection.execute(
                "INSERT INTO leads (id, tenant_id, source_id, first_name, last_name, "
                "company, budget, industry, score, status) "
                "VALUES (%s, %s, %s, 'A', 'B', 'C', %s, 'tech', 0, 'NEW')",
                (uuid4(), tenant.id.value, uuid4(), 10 ** 13),
            )

    assert exc_info.value.error_code == "AMOUNT_OUT_OF_RANGE"
    assert not isinstance(exc_info.value, psycopg.errors.NumericValueOutOfRange)
