from contextlib import contextmanager
from datetime import timezone
from typing import Iterator
from uuid import UUID

from chassis.outbox import OutboxRow, OutboxStore
from chassis.persistence import RawSqlDatabase

from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork


class UnitOfWorkOutboxStore:
    """Gives the chassis relay the outbox of an open unit of work."""

    def __init__(self, outbox: OutboxRepositoryPort) -> None:
        self._outbox = outbox

    def fetch(self, channel: str, limit: int) -> list[OutboxRow]:
        return [
            OutboxRow(
                id=entry.id,
                channel=entry.channel,
                tenant_id=entry.tenant_id,
                partition_key=entry.partition_key,
                event_type=entry.event_type,
                payload=entry.payload,
                # A naive timestamp would serialize without an offset and be
                # read as local time by whoever consumes the envelope.
                occurred_on=(
                    entry.occurred_on if entry.occurred_on.tzinfo
                    else entry.occurred_on.replace(tzinfo=timezone.utc)
                ),
                correlation_id=entry.correlation_id,
            )
            for entry in self._outbox.list_unpublished(channel, limit)
        ]

    def mark_published(self, row_id: UUID) -> None:
        self._outbox.mark_published(row_id)

    def mark_failed(self, row_id: UUID, error: str) -> None:
        self._outbox.mark_failed(row_id, error)


@contextmanager
def open_outbox_store(database: RawSqlDatabase) -> Iterator[OutboxStore]:
    """One transaction per use: committed on exit, so the relay's marks persist."""
    with PostgresUnitOfWork(database) as uow:
        yield UnitOfWorkOutboxStore(uow.outbox)
