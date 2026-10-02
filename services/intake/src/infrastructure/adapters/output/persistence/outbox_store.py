from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timezone
from uuid import UUID

import psycopg
from chassis.outbox import OutboxRow, OutboxStore
from chassis.persistence import RawSqlDatabase

from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork


class PostgresOutboxStore:
    """What the chassis relay reads and marks; writing is the repository's job."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def fetch(self, channel: str, limit: int) -> list[OutboxRow]:
        # No row lock: the relay closes this transaction before it delivers, so a
        # lock would be released long before the broker call it was meant to cover.
        # Two relays racing may deliver a row twice, which event_id lets a consumer
        # deduplicate.
        #
        # Fewest attempts first, and nothing is ever dropped for having been
        # retried: a failing row sinks in the order instead of starving the rest.
        # That reordering is only across keys. Within one partition_key only the
        # oldest unpublished row is eligible: on a compacted topic the last record
        # wins, so letting v6 out before a failing v5 would leave the older state
        # as the final one. (occurred_on, id) keeps equal timestamps total.
        rows = self._connection.execute(
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
            OutboxRow(
                id=row["id"],
                channel=row["channel"],
                tenant_id=str(row["tenant_id"]) if row["tenant_id"] is not None else None,
                partition_key=row["partition_key"],
                event_type=row["event_type"],
                payload=row["payload"],
                # A naive timestamp would serialize without an offset and be
                # read as local time by whoever consumes the envelope.
                occurred_on=(
                    row["occurred_on"] if row["occurred_on"].tzinfo
                    else row["occurred_on"].replace(tzinfo=timezone.utc)
                ),
                correlation_id=row["correlation_id"],
            )
            for row in rows
        ]

    def mark_published(self, row_id: UUID) -> None:
        self._connection.execute("UPDATE outbox_events SET published_at = now() WHERE id = %s", (row_id,))

    def mark_failed(self, row_id: UUID, error: str) -> None:
        self._connection.execute(
            "UPDATE outbox_events SET attempts = attempts + 1, last_error = %s WHERE id = %s", (error, row_id),
        )


@contextmanager
def open_outbox_store(database: RawSqlDatabase) -> Iterator[OutboxStore]:
    """One transaction per use: committed on exit, so the relay's marks persist."""
    with PostgresUnitOfWork(database) as uow:
        yield PostgresOutboxStore(uow.connection)
