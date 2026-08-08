from typing import List, Optional
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.intake_record_repository_port import IntakeRecordRepositoryPort
from domain.entities.intake_record import IntakeError, IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus


class RawSqlIntakeRecordRepository(IntakeRecordRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, record: IntakeRecord) -> IntakeRecord:
        self.connection.execute(
            """
            INSERT INTO intake_records (
                id, tenant_id, source_id, payload, status, lead_id, received_at, processed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                payload = EXCLUDED.payload,
                status = EXCLUDED.status,
                lead_id = EXCLUDED.lead_id,
                processed_at = EXCLUDED.processed_at
            """,
            (
                record.id.value,
                record.tenant_id.value,
                record.source_id.value,
                Jsonb(record.payload),
                record.status.value,
                record.lead_id.value if record.lead_id else None,
                record.received_at,
                record.processed_at,
            ),
        )
        # Errors are values owned by the record, not entities with their own
        # identity: reconciling row-by-row would be work without benefit.
        self.connection.execute(
            "DELETE FROM intake_errors WHERE intake_record_id = %s",
            (record.id.value,),
        )
        for error in record.errors:
            self.connection.execute(
                """
                INSERT INTO intake_errors (id, intake_record_id, field, message, received_value, error_code)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid4(),
                    record.id.value,
                    error.field,
                    error.message,
                    error.received_value,
                    error.error_code,
                ),
            )
        return record

    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        row = self.connection.execute(
            "SELECT * FROM intake_records WHERE id = %s AND tenant_id = %s",
            (record_id, tenant_id),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeRecord]:
        if status is not None:
            rows = self.connection.execute(
                "SELECT * FROM intake_records WHERE tenant_id = %s AND status = %s "
                "ORDER BY received_at, id LIMIT %s OFFSET %s",
                (tenant_id, status.value, limit, offset),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM intake_records WHERE tenant_id = %s "
                "ORDER BY received_at, id LIMIT %s OFFSET %s",
                (tenant_id, limit, offset),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None) -> int:
        if status is not None:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count FROM intake_records WHERE tenant_id = %s AND status = %s",
                (tenant_id, status.value),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count FROM intake_records WHERE tenant_id = %s",
                (tenant_id,),
            ).fetchone()
        return row["count"]

    def _row_to_record(self, row) -> IntakeRecord:
        # Paginated 100 at a time and opened a few times a day: a per-record
        # query is simpler than a JOIN and the volume never makes it a cost.
        error_rows = self.connection.execute(
            "SELECT field, message, received_value, error_code FROM intake_errors "
            "WHERE intake_record_id = %s",
            (row["id"],),
        ).fetchall()
        return IntakeRecord.create(
            record_id=row["id"],
            tenant_id=row["tenant_id"],
            source_id=row["source_id"],
            payload=row["payload"],
            status=row["status"],
            errors=[
                IntakeError(
                    field=e["field"],
                    message=e["message"],
                    received_value=e["received_value"],
                    error_code=e["error_code"],
                )
                for e in error_rows
            ],
            lead_id=row["lead_id"],
            received_at=row["received_at"],
            processed_at=row["processed_at"],
        )
