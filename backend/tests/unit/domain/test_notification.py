import uuid
from typing import Any

import pytest

from domain.entities.notification import Notification
from domain.exceptions import DomainException
from domain.value_objects.enums import NotificationKind
from domain.value_objects.lead_id import LeadId

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
    def test_creates_unread_with_a_timestamp(self):
        notification = _notification()
        assert notification.is_read is False
        assert notification.created_at is not None

    def test_an_empty_message_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _notification(message="")
        assert exc.value.error_code == "INVALID_NOTIFICATION_MESSAGE"

    def test_a_whitespace_only_message_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _notification(message="   ")
        assert exc.value.error_code == "INVALID_NOTIFICATION_MESSAGE"

    def test_lead_id_accepts_str_uuid_and_value_object(self):
        raw = uuid.uuid4()
        as_str = _notification(lead_id=str(raw))
        as_uuid = _notification(lead_id=raw)
        as_vo = _notification(lead_id=LeadId(raw))
        assert as_str.lead_id.value == raw
        assert as_uuid.lead_id.value == raw
        assert as_vo.lead_id.value == raw

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
