import uuid
from typing import Any

import pytest

from domain.exceptions import DomainException
from domain.notifications.kind import NotificationKind
from domain.notifications.notification import Notification

_TENANT = uuid.uuid4()
_RECIPIENT = uuid.uuid4()


def _notification(**overrides: Any) -> Notification:
    base = dict(
        tenant_id=_TENANT,
        recipient_id=_RECIPIENT,
        kind=NotificationKind.LEAD_ASSIGNED,
        message="Tienes un lead nuevo asignado",
    )
    base.update(overrides)
    return Notification.create(**base)


class TestCreate:
    def test_creates_unread_with_a_timestamp_and_an_id(self):
        notification = _notification()
        assert notification.is_read is False
        assert notification.created_at is not None
        assert isinstance(notification.id, uuid.UUID)

    def test_an_empty_message_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _notification(message="")
        assert exc.value.error_code == "INVALID_NOTIFICATION_MESSAGE"

    def test_a_whitespace_only_message_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _notification(message="   ")
        assert exc.value.error_code == "INVALID_NOTIFICATION_MESSAGE"

    def test_the_message_is_stripped(self):
        assert _notification(message="  hola  ").message == "hola"

    def test_identifiers_accept_str_and_uuid(self):
        raw = uuid.uuid4()
        assert _notification(lead_id=str(raw)).lead_id == raw
        assert _notification(lead_id=raw).lead_id == raw
        assert _notification(recipient_id=str(raw)).recipient_id == raw
        assert _notification(tenant_id=str(raw)).tenant_id == raw

    def test_the_kind_accepts_its_value(self):
        assert _notification(kind="INTAKE_REJECTED").kind is NotificationKind.INTAKE_REJECTED

    def test_an_invalid_identifier_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _notification(lead_id="not-a-uuid")
        assert exc.value.error_code == "INVALID_IDENTIFIER"

    def test_without_lead_id_or_intake_record_id_both_are_none(self):
        notification = _notification()
        assert notification.lead_id is None
        assert notification.intake_record_id is None


class TestMarkAsRead:
    def test_marks_an_unread_notification(self):
        notification = _notification()
        notification.mark_as_read()
        assert notification.is_read is True

    def test_is_idempotent(self):
        notification = _notification()
        notification.mark_as_read()
        notification.mark_as_read()
        assert notification.is_read is True
