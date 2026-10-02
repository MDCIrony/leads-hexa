from uuid import uuid4

import pytest

from application.use_cases.notifications.notification_handler import NotificationHandler
from domain.members.member import Member
from domain.notifications.kind import NotificationKind
from domain.notifications.notification import Notification
from infrastructure.adapters.input.consumers.notification_consumer import NotificationConsumer

from .events import count, event

_GROUP = "notifications.lead-events"


def test_the_same_envelope_twice_creates_one_notification(test_db, uow_factory):
    agent_id, tenant_id = uuid4(), uuid4()
    message = event("LeadAssigned", tenant_id, {"lead_id": str(uuid4()), "agent_id": str(agent_id)})
    consumer = NotificationConsumer(uow_factory, _GROUP)

    consumer(message)
    consumer(message)

    assert count(test_db, "SELECT COUNT(*) AS n FROM notifications WHERE recipient_id = %s", (agent_id,)) == 1


def test_a_failing_effect_leaves_no_processed_row_and_no_notification(test_db, uow_factory, monkeypatch):
    """The mark and the effect share one transaction: if the mark committed and the effect failed,
    the retry would see the event as done and the notice would be lost for good."""
    message = event("LeadAssigned", uuid4(), {"lead_id": str(uuid4()), "agent_id": str(uuid4())})

    def boom(self, event_type, tenant_id, payload, uow):
        # Write first, then fail: the empty table below proves the rollback, not an idle handler.
        uow.notifications.save(Notification.create(
            tenant_id=tenant_id, recipient_id=uuid4(), kind=NotificationKind.LEAD_ASSIGNED, message="Doomed"))
        raise RuntimeError("effect failed")

    monkeypatch.setattr(NotificationHandler, "apply", boom)
    with pytest.raises(RuntimeError):
        NotificationConsumer(uow_factory, _GROUP)(message)

    assert count(test_db, "SELECT COUNT(*) AS n FROM processed_events WHERE event_id = %s", (message.event_id,)) == 0
    assert count(test_db, "SELECT COUNT(*) AS n FROM notifications") == 0


def test_a_lead_left_unassigned_reaches_the_active_managers_of_the_tenant_and_nobody_else(test_db, uow_factory):
    tenant_id, other_tenant_id = uuid4(), uuid4()
    managers = [uuid4(), uuid4()]
    with uow_factory() as uow:
        for manager_id in managers:
            uow.members.save(Member(manager_id, tenant_id, "MANAGER", True, 1))
        uow.members.save(Member(uuid4(), tenant_id, "MANAGER", False, 1))
        uow.members.save(Member(uuid4(), tenant_id, "AGENT", True, 1))
        uow.members.save(Member(uuid4(), other_tenant_id, "MANAGER", True, 1))

    NotificationConsumer(uow_factory, _GROUP)(event("LeadLeftUnassigned", tenant_id, {"lead_id": str(uuid4())}))

    with test_db.get_connection(autocommit=True) as conn:
        recipients = {row["recipient_id"] for row in conn.execute("SELECT recipient_id FROM notifications")}
    assert recipients == set(managers)
