"""Helpers shared by the consumer integration tests."""
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from chassis.consumer import Envelope
from chassis.outbox import OutboxRow, envelope


def event_bytes(event_type: str, tenant_id: UUID, payload: dict) -> bytes:
    """Built the way the relay builds it, so the tests read what a Kafka consumer reads."""
    row = OutboxRow(
        id=uuid4(), channel="internal", tenant_id=str(tenant_id), partition_key=str(uuid4()),
        event_type=event_type, payload=payload, occurred_on=datetime.now(timezone.utc), correlation_id=None,
    )
    return json.dumps(envelope(row, "lead-core")).encode()


def event(event_type: str, tenant_id: UUID, payload: dict) -> Envelope:
    return Envelope.from_bytes(event_bytes(event_type, tenant_id, payload))


def count(test_db, sql: str, params: tuple = ()) -> int:
    with test_db.get_connection(autocommit=True) as conn:
        return conn.execute(sql, params).fetchone()["n"]
