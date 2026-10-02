import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.outbox import OutboxRepositoryPort
from domain.events.internal_event import InternalEvent
from infrastructure.adapters.output.persistence.correlation import current_correlation_id


class PostgresOutboxRepository(OutboxRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def record(self, event: InternalEvent, channel: str = "internal") -> None:
        # The correlation id is read here, not passed in: only the adapter sees the request.
        self.connection.execute(
            """
            INSERT INTO outbox_events (
                id, tenant_id, partition_key, event_type, payload, occurred_on, channel, correlation_id
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
