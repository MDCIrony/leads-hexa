from uuid import UUID

import psycopg

from application.ports.output.processed_event_repository import ProcessedEventRepositoryPort


class PostgresProcessedEventRepository(ProcessedEventRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def mark(self, consumer: str, event_id: UUID) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO processed_events (consumer, event_id)
            VALUES (%s, %s)
            ON CONFLICT (consumer, event_id) DO NOTHING
            """,
            (consumer, event_id),
        )
        return cursor.rowcount == 1
