import json

import pytest

from chassis.consumer import Envelope
from consumer.helpers import body, raw


def test_envelope_from_bytes_parses_a_valid_message():
    values = body()

    parsed = Envelope.from_bytes(json.dumps(values).encode())

    assert str(parsed.event_id) == values["event_id"]
    assert (parsed.event_type, parsed.schema_version, parsed.producer) == ("LeadAssigned", 1, "lead-core")
    assert (parsed.tenant_id, parsed.aggregate_id, parsed.correlation_id) == ("t-1", "lead-9", "corr-1")
    assert parsed.payload == {"lead_id": "lead-9"}


def test_envelope_accepts_null_tenant_and_correlation():
    parsed = Envelope.from_bytes(raw(tenant_id=None, correlation_id=None))

    assert parsed.tenant_id is None and parsed.correlation_id is None


@pytest.mark.parametrize("value", [
    b"\xff\xfe not utf8", b"not json", b"[]", b"null",
    json.dumps({k: v for k, v in body().items() if k != "event_type"}).encode(),
    raw(event_id="not-a-uuid"),
    raw(schema_version="1"),
    raw(payload=[1]),
    raw(event_type=3),
])
def test_envelope_rejects_anything_malformed(value):
    with pytest.raises(ValueError):
        Envelope.from_bytes(value)
