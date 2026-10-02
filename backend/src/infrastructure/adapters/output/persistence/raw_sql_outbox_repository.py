from typing import List
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.dtos.commands import OutboxEntry
from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from domain.events.internal_event import InternalEvent
from domain.events.lead_events import OutboundEvent
from infrastructure.adapters.output.persistence.correlation import current_correlation_id

class RawSqlOutboxRepository(OutboxRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def record(self, event: OutboundEvent | InternalEvent, channel: str = "product") -> None:
        # Read here and not passed in: the application has no notion of the
        # request that triggered the event, only the adapter sees the ContextVar.
        self.connection.execute(
            """
            INSERT INTO outbox_events (
                id, tenant_id, partition_key, event_type, payload, occurred_on,
                channel, correlation_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event.event_id,
                event.tenant_id,
                event.partition_key,
                event.event_type,
                Jsonb(event.as_payload()),
                event.occurred_on,
                channel,
                current_correlation_id(),
            ),
        )

    def list_unpublished(self, channel: str, limit: int) -> List[OutboxEntry]:
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
        #
        # That reordering is only across keys. Within one partition_key only
        # the oldest unpublished row is eligible: on a compacted topic the
        # last record wins, so letting v6 out before a failing v5 would leave
        # the older state as the final one. A poison row blocks its own key
        # and nothing else. (occurred_on, id) keeps equal timestamps total.
        rows = self.connection.execute(
            """
            SELECT o.id, o.tenant_id, o.partition_key, o.event_type, o.payload,
                   o.occurred_on, o.channel, o.correlation_id
            FROM outbox_events o
            WHERE o.channel = %s AND o.published_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM outbox_events p
                  WHERE p.channel = o.channel AND p.partition_key = o.partition_key
                    AND p.published_at IS NULL
                    AND (p.occurred_on, p.id) < (o.occurred_on, o.id)
              )
            ORDER BY o.attempts, o.occurred_on
            LIMIT %s
            """,
            (channel, limit),
        ).fetchall()
        return [
            OutboxEntry(
                id=row["id"],
                tenant_id=str(row["tenant_id"]) if row["tenant_id"] is not None else None,
                partition_key=row["partition_key"],
                event_type=row["event_type"],
                payload=row["payload"],
                occurred_on=row["occurred_on"],
                channel=row["channel"],
                correlation_id=row["correlation_id"],
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
