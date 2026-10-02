from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID

from domain.events.domain_event import DomainEvent


class _Color(Enum):
    RED = "red"


@dataclass(kw_only=True)
class _Everything(DomainEvent):
    some_id: UUID
    at: datetime
    color: _Color
    amount: Decimal
    nested: dict
    items: list


def test_the_payload_turns_every_value_kind_into_what_json_can_hold():
    some_id = UUID("11111111-1111-1111-1111-111111111111")
    at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    payload = _Everything(
        some_id=some_id, at=at, color=_Color.RED, amount=Decimal("10.50"),
        nested={"id": some_id, "inner": {"color": _Color.RED}}, items=[at, Decimal("0.1"), "plain"],
    ).as_payload()

    assert payload["some_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["at"] == "2026-01-02T03:04:05+00:00"
    assert payload["color"] == "red"
    # A string, not a float: exactness is what a Decimal field exists to protect.
    assert payload["amount"] == "10.50"
    assert payload["nested"] == {"id": "11111111-1111-1111-1111-111111111111", "inner": {"color": "red"}}
    assert payload["items"] == ["2026-01-02T03:04:05+00:00", "0.1", "plain"]
    assert isinstance(payload["event_id"], str) and isinstance(payload["occurred_on"], str)
