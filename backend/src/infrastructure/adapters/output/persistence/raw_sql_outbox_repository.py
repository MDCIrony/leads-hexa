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
        # No row lock: the relay closes this transaction before it delivers,
        # so a lock would be released long before the HTTP call it was meant
        # to cover. Two relays racing may deliver the same entry twice, which
        # is what at-least-once means and what event_id lets a consumer
        # deduplicate — holding the transaction open across the network to
        # avoid it would cost the pool the API runs on.
        #
        # Fewest attempts first, and nothing is ever dropped for having been
        # retried too often. Ordering by age alone let a permanently broken
        # destination sort first forever and starve everything behind it; a
        # retry cap would have been worse — a broker down for a few seconds
        # would exhaust it and lose exactly the leads this table exists to
        # protect. A failing entry sinks in the order instead, so new ones
        # overtake it, and it keeps being retried for as long as it takes.
        rows = self.connection.execute(
            """
            SELECT id, tenant_id, partition_key, event_type, payload, occurred_on
            FROM outbox_events
            WHERE published_at IS NULL
            ORDER BY attempts, occurred_on
            LIMIT %s
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
