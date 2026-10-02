from datetime import datetime, timezone
from uuid import UUID, uuid4

from chassis.consumer import Envelope

from infrastructure.adapters.input.consumers.member_consumer import MemberConsumer


def agent_state(tenant_id: UUID | None, agent_id: UUID, version: int, role="MANAGER", event_type="AgentState") -> Envelope:
    return Envelope(
        event_id=uuid4(), event_type=event_type, schema_version=1,
        occurred_at=datetime.now(timezone.utc).isoformat(), producer="identity",
        tenant_id=str(tenant_id) if tenant_id else None, aggregate_id=str(agent_id), correlation_id=None,
        payload={"agent_id": str(agent_id), "role": role, "is_active": True, "version": version},
    )


def test_versions_two_one_three_leave_the_third(uow_factory):
    tenant_id, agent_id = uuid4(), uuid4()
    consumer = MemberConsumer(uow_factory)

    consumer(agent_state(tenant_id, agent_id, 2, role="AGENT"))
    consumer(agent_state(tenant_id, agent_id, 1, role="ADMIN"))
    consumer(agent_state(tenant_id, agent_id, 3, role="MANAGER"))

    with uow_factory() as uow:
        member = uow.members.get(agent_id)
    assert (member.version, member.role) == (3, "MANAGER")


def test_the_platform_administrator_without_a_tenant_leaves_no_row(test_db, uow_factory):
    MemberConsumer(uow_factory)(agent_state(None, uuid4(), 1))

    with test_db.get_connection(autocommit=True) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM members").fetchone()["n"] == 0


def test_other_event_types_are_ignored(test_db, uow_factory):
    MemberConsumer(uow_factory)(agent_state(uuid4(), uuid4(), 1, event_type="TenantState"))

    with test_db.get_connection(autocommit=True) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM members").fetchone()["n"] == 0


def test_the_projection_does_not_mark_processed_events(test_db, uow_factory):
    MemberConsumer(uow_factory)(agent_state(uuid4(), uuid4(), 1))

    with test_db.get_connection(autocommit=True) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM processed_events").fetchone()["n"] == 0
