from uuid import uuid4

import psycopg
import pytest

from domain.entities.agent import Agent
from domain.entities.rule import AssignmentRule
from domain.entities.tenant import Tenant
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy
from infrastructure.adapters.output.persistence.postgres_unit_of_work import (
    PostgresUnitOfWork,
)
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)


def _tenant(test_db) -> Tenant:
    with test_db.get_connection(autocommit=True) as conn:
        return RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))


def test_unique_violation_is_translated_to_already_exists(test_db):
    """A UniqueViolation raised inside the unit of work, bypassing any use
    case pre-check, must reach the caller as a DomainException — never as
    the raw psycopg error the exception_handlers module cannot recognize."""
    tenant = _tenant(test_db)
    uow = PostgresUnitOfWork(test_db)

    with pytest.raises(DomainException) as exc_info:
        with uow:
            uow.agents.save(Agent.create(name="A", email="dup@a.test", tenant_id=tenant.id.value))
            uow.agents.save(Agent.create(name="B", email="dup@a.test", tenant_id=tenant.id.value))

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
    agent = Agent.create(name="A", email=f"{uuid4()}@a.test", tenant_id=tenant.id.value)
    uow = PostgresUnitOfWork(test_db)
    with uow:
        uow.agents.save(agent)

    with pytest.raises(DomainException) as exc_info:
        with uow:
            uow.connection.execute(
                "UPDATE agents SET name = NULL WHERE id = %s", (agent.id.value,)
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
            uow.agents.save(Agent.create(name="A", email="dup2@a.test", tenant_id=tenant.id.value))
            uow.agents.save(Agent.create(name="B", email="dup2@a.test", tenant_id=tenant.id.value))

    with uow:
        uow.agents.save(Agent.create(name="C", email="ok@a.test", tenant_id=tenant.id.value))

    with test_db.get_connection(autocommit=True) as conn:
        row = conn.execute(
            "SELECT email FROM agents WHERE tenant_id = %s", (tenant.id.value,)
        ).fetchall()
    assert {r["email"] for r in row} == {"ok@a.test"}
