import psycopg
from chassis.web import request_id_var
from psycopg.types.json import Jsonb

from application.ports.output.outbox import OutboxRepositoryPort
from domain.events.internal_event import InternalEvent


def current_correlation_id() -> str | None:
    """The id of the request in flight, or None outside one.

    "-" is the ContextVar's default, not an id: storing it would make every
    background write look like it belonged to the same request."""
    request_id = request_id_var.get()
    return None if request_id == "-" else request_id


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
