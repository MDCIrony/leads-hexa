from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg

from domain.entities.agent import Agent
from domain.entities.notification import Notification
from domain.entities.tenant import Tenant
from domain.value_objects.enums import AgentRole, NotificationKind
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import (
    RawSqlAgentRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_notification_repository import (
    RawSqlNotificationRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlNotificationRepository(conn), conn, ctx


def _tenant(conn: psycopg.Connection) -> Tenant:
    # notifications.tenant_id has a foreign key to tenants (migration 008).
    return RawSqlTenantRepository(conn).save(Tenant.create(name=f"Org {uuid4()}"))


def _agent(conn: psycopg.Connection, tenant_id) -> Agent:
    # notifications.recipient_id has a foreign key to agents (migration 008).
    return RawSqlAgentRepository(conn).save(
        Agent.create(f"Agent {uuid4()}", f"{uuid4()}@test.com", role=AgentRole.AGENT, tenant_id=tenant_id)
    )


def test_saves_and_reads_back_every_field_including_nulls(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        agent = _agent(conn, tenant.id.value)
        lead_id = uuid4()
        saved = repo.save(
            Notification.create(
                tenant_id=tenant.id.value,
                recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED,
                message="Tienes un lead nuevo asignado",
                lead_id=lead_id,
            )
        )

        found = repo.get_by_id_and_recipient(saved.id.value, agent.id.value)
        assert found is not None
        assert found.tenant_id.value == tenant.id.value
        assert found.recipient_id.value == agent.id.value
        assert found.kind == NotificationKind.LEAD_ASSIGNED
        assert found.message == "Tienes un lead nuevo asignado"
        assert found.is_read is False
        assert found.lead_id.value == lead_id
        assert found.intake_record_id is None
    finally:
        ctx.__exit__(None, None, None)


def test_list_by_recipient_with_unread_only_returns_only_unread(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        agent = _agent(conn, tenant.id.value)
        unread = repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Uno",
            )
        )
        read = repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Dos",
            )
        )
        read.mark_as_read()
        repo.save(read)

        everything = repo.list_by_recipient(agent.id.value)
        unread_only = repo.list_by_recipient(agent.id.value, unread_only=True)

        assert {n.id.value for n in everything} == {unread.id.value, read.id.value}
        assert {n.id.value for n in unread_only} == {unread.id.value}
    finally:
        ctx.__exit__(None, None, None)


def test_count_by_recipient_with_and_without_filter(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        agent = _agent(conn, tenant.id.value)
        repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Uno",
            )
        )
        read = repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Dos",
            )
        )
        read.mark_as_read()
        repo.save(read)

        assert repo.count_by_recipient(agent.id.value) == 2
        assert repo.count_by_recipient(agent.id.value, unread_only=True) == 1
    finally:
        ctx.__exit__(None, None, None)


def test_get_by_id_and_recipient_of_another_recipient_returns_none(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        agent = _agent(conn, tenant.id.value)
        other = _agent(conn, tenant.id.value)
        saved = repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Uno",
            )
        )

        assert repo.get_by_id_and_recipient(saved.id.value, agent.id.value) is not None
        assert repo.get_by_id_and_recipient(saved.id.value, other.id.value) is None
    finally:
        ctx.__exit__(None, None, None)


def test_mark_all_read_returns_how_many_and_a_second_call_returns_zero(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        agent = _agent(conn, tenant.id.value)
        repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Uno",
            )
        )
        repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Dos",
            )
        )

        assert repo.mark_all_read(agent.id.value) == 2
        assert repo.mark_all_read(agent.id.value) == 0
    finally:
        ctx.__exit__(None, None, None)


def test_list_by_recipient_orders_newest_first(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        tenant = _tenant(conn)
        agent = _agent(conn, tenant.id.value)
        base = datetime.now(timezone.utc)
        first = repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Primero",
                created_at=base,
            )
        )
        second = repo.save(
            Notification.create(
                tenant_id=tenant.id.value, recipient_id=agent.id.value,
                kind=NotificationKind.LEAD_ASSIGNED, message="Segundo",
                created_at=base + timedelta(seconds=1),
            )
        )

        found = repo.list_by_recipient(agent.id.value)

        assert [n.id.value for n in found] == [second.id.value, first.id.value]
    finally:
        ctx.__exit__(None, None, None)
