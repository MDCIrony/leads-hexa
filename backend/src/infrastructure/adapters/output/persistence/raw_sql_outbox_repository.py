from typing import List
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.dtos.commands import OutboxEntry
from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from domain.events.lead_events import OutboundEvent


class RawSqlOutboxRepository(OutboxRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def record(self, event: OutboundEvent) -> None:
        self.connection.execute(
            """
            INSERT INTO outbox_events (
                id, tenant_id, partition_key, event_type, payload, occurred_on
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                event.event_id,
                event.tenant_id,
                event.partition_key,
                event.event_type,
                Jsonb(event.as_payload()),
                event.occurred_on,
            ),
        )

    def list_unpublished(self, limit: int) -> List[OutboxEntry]:
        # FOR UPDATE SKIP LOCKED: two relays (or two replicas of this
        # process) racing this query must not both walk away with the same
        # row, without one of them blocking on the other's lock.
        rows = self.connection.execute(
            """
            SELECT id, tenant_id, partition_key, event_type, payload, occurred_on
            FROM outbox_events
            WHERE published_at IS NULL
            ORDER BY occurred_on
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (limit,),
        ).fetchall()
        return [
            OutboxEntry(
                id=row["id"],
                tenant_id=str(row["tenant_id"]),
                partition_key=row["partition_key"],
                event_type=row["event_type"],
                payload=row["payload"],
                occurred_on=row["occurred_on"],
            )
            for row in rows
        ]

    def mark_published(self, event_id: UUID) -> None:
        self.connection.execute(
            "UPDATE outbox_events SET published_at = now() WHERE id = %s",
            (event_id,),
        )

    def mark_failed(self, event_id: UUID, error: str) -> None:
        self.connection.execute(
            "UPDATE outbox_events SET attempts = attempts + 1, last_error = %s WHERE id = %s",
            (error, event_id),
        )
