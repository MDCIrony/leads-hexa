from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.notifications.kind import NotificationKind
from domain.notifications.notification import Notification


def _notice(tenant_id, recipient_id, message="Uno", **fields) -> Notification:
    return Notification.create(
        tenant_id=tenant_id, recipient_id=recipient_id, kind=NotificationKind.LEAD_ASSIGNED,
        message=message, **fields,
    )


def test_saves_and_reads_back_every_field_including_nulls(uow_factory):
    tenant_id, recipient_id, lead_id = uuid4(), uuid4(), uuid4()
    with uow_factory() as uow:
        saved = uow.notifications.save(
            _notice(tenant_id, recipient_id, "Tienes un lead nuevo asignado", lead_id=lead_id)
        )

        found = uow.notifications.get_by_id_and_recipient(saved.id, recipient_id)

    assert found is not None
    assert found.tenant_id == tenant_id
    assert found.recipient_id == recipient_id
    assert found.kind == NotificationKind.LEAD_ASSIGNED
    assert found.message == "Tienes un lead nuevo asignado"
    assert found.is_read is False
    assert found.lead_id == lead_id
    assert found.intake_record_id is None


def test_list_with_unread_only_returns_only_unread(uow_factory):
    tenant_id, recipient_id = uuid4(), uuid4()
    with uow_factory() as uow:
        unread = uow.notifications.save(_notice(tenant_id, recipient_id, "Uno"))
        read = uow.notifications.save(_notice(tenant_id, recipient_id, "Dos"))
        read.mark_as_read()
        uow.notifications.save(read)

        everything = uow.notifications.list_by_recipient(recipient_id)
        unread_only = uow.notifications.list_by_recipient(recipient_id, unread_only=True)

    assert {n.id for n in everything} == {unread.id, read.id}
    assert {n.id for n in unread_only} == {unread.id}


def test_count_with_and_without_filter(uow_factory):
    tenant_id, recipient_id = uuid4(), uuid4()
    with uow_factory() as uow:
        uow.notifications.save(_notice(tenant_id, recipient_id, "Uno"))
        read = uow.notifications.save(_notice(tenant_id, recipient_id, "Dos"))
        read.mark_as_read()
        uow.notifications.save(read)

        assert uow.notifications.count_by_recipient(recipient_id) == 2
        assert uow.notifications.count_by_recipient(recipient_id, unread_only=True) == 1


def test_a_notice_of_another_recipient_is_not_found(uow_factory):
    tenant_id, recipient_id, other_id = uuid4(), uuid4(), uuid4()
    with uow_factory() as uow:
        saved = uow.notifications.save(_notice(tenant_id, recipient_id))

        assert uow.notifications.get_by_id_and_recipient(saved.id, recipient_id) is not None
        assert uow.notifications.get_by_id_and_recipient(saved.id, other_id) is None


def test_mark_all_read_returns_how_many_and_a_second_call_returns_zero(uow_factory):
    tenant_id, recipient_id = uuid4(), uuid4()
    with uow_factory() as uow:
        uow.notifications.save(_notice(tenant_id, recipient_id, "Uno"))
        uow.notifications.save(_notice(tenant_id, recipient_id, "Dos"))

        assert uow.notifications.mark_all_read(recipient_id) == 2
        assert uow.notifications.mark_all_read(recipient_id) == 0


def test_list_orders_newest_first(uow_factory):
    tenant_id, recipient_id = uuid4(), uuid4()
    base = datetime.now(timezone.utc)
    with uow_factory() as uow:
        first = uow.notifications.save(_notice(tenant_id, recipient_id, "Primero", created_at=base))
        second = uow.notifications.save(
            _notice(tenant_id, recipient_id, "Segundo", created_at=base + timedelta(seconds=1))
        )

        found = uow.notifications.list_by_recipient(recipient_id)

    assert [n.id for n in found] == [second.id, first.id]


def test_pagination_applies_limit_and_offset(uow_factory):
    tenant_id, recipient_id = uuid4(), uuid4()
    base = datetime.now(timezone.utc)
    with uow_factory() as uow:
        saved = [
            uow.notifications.save(_notice(tenant_id, recipient_id, str(i), created_at=base + timedelta(seconds=i)))
            for i in range(3)
        ]

        page = uow.notifications.list_by_recipient(recipient_id, limit=1, offset=1)

    assert [n.id for n in page] == [saved[1].id]
