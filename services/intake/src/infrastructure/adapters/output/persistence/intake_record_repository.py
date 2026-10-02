from typing import Any, List, Optional
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.records import IntakeRecordRepositoryPort
from domain.records.intake_record import IntakeError, IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from infrastructure.adapters.output.persistence.record_payload import json_safe


class PostgresIntakeRecordRepository(IntakeRecordRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, record: IntakeRecord) -> IntakeRecord:
        self.connection.execute(
            """
            INSERT INTO intake_records (
                id, tenant_id, source_id, job_id, payload, status, lead_id, received_at, processed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                record.job_id.value if record.job_id else None,
                Jsonb(json_safe(record.payload)),
                record.status.value,
                record.lead_id.value if record.lead_id else None,
                record.received_at,
                record.processed_at,
            ),
        )
        # Errors are values owned by the record, not entities with their own
        # identity: replacing the set is simpler than reconciling row by row.
        self.connection.execute("DELETE FROM intake_errors WHERE intake_record_id = %s", (record.id.value,))
        for error in record.errors:
            self.connection.execute(
                """
                INSERT INTO intake_errors (id, intake_record_id, field, message, received_value, error_code)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (uuid4(), record.id.value, error.field, error.message, error.received_value, error.error_code),
            )
        return record

    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        row = self.connection.execute(
            "SELECT * FROM intake_records WHERE id = %s AND tenant_id = %s", (record_id, tenant_id),
        ).fetchone()
        return self._to_records([row])[0] if row else None

    def claim_unpromoted(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        # FOR UPDATE with the status in the WHERE: a second transaction blocks here
        # until the first commits, then re-evaluates the condition under READ
        # COMMITTED, sees PROMOTED (or DISCARDED) and gets nothing back instead of
        # closing the record a second time.
        row = self.connection.execute(
            """
            SELECT * FROM intake_records
            WHERE id = %s AND tenant_id = %s AND status IN ('PENDING', 'REJECTED')
            FOR UPDATE
            """,
            (record_id, tenant_id),
        ).fetchone()
        return self._to_records([row])[0] if row else None

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        job_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeRecord]:
        where, params = _filter(tenant_id, status, job_id)
        rows = self.connection.execute(
            "SELECT * FROM intake_records" + where + " ORDER BY received_at DESC, id LIMIT %s OFFSET %s",
            [*params, limit, offset],
        ).fetchall()
        return self._to_records(rows)

    def count_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None, job_id: Optional[UUID] = None,
    ) -> int:
        where, params = _filter(tenant_id, status, job_id)
        return self.connection.execute(
            "SELECT COUNT(*) AS count FROM intake_records" + where, params,
        ).fetchone()["count"]

    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        return self.connection.execute(
            "SELECT COUNT(*) AS count FROM intake_records WHERE tenant_id = %s AND source_id = %s",
            (tenant_id, source_id),
        ).fetchone()["count"]

    def _to_records(self, rows) -> List[IntakeRecord]:
        # One query for the errors of the whole page: a worker run reads thousands of
        # records, and a query per record would be thousands of round trips.
        errors_by_record: dict[UUID, List[IntakeError]] = {}
        if rows:
            error_rows = self.connection.execute(
                "SELECT intake_record_id, field, message, received_value, error_code "
                "FROM intake_errors WHERE intake_record_id = ANY(%s)",
                ([row["id"] for row in rows],),
            ).fetchall()
            for e in error_rows:
                errors_by_record.setdefault(e["intake_record_id"], []).append(IntakeError(
                    field=e["field"], message=e["message"],
                    received_value=e["received_value"], error_code=e["error_code"],
                ))
        return [
            IntakeRecord.create(
                record_id=row["id"],
                tenant_id=row["tenant_id"],
                source_id=row["source_id"],
                payload=row["payload"],
                status=row["status"],
                errors=errors_by_record.get(row["id"], []),
                lead_id=row["lead_id"],
                received_at=row["received_at"],
                processed_at=row["processed_at"],
                job_id=row["job_id"],
            )
            for row in rows
        ]


def _filter(tenant_id: UUID, status: Optional[IntakeRecordStatus], job_id: Optional[UUID]) -> tuple[str, List[Any]]:
    # Two independent optional filters: built up instead of four near-identical
    # queries. Only fixed clauses are concatenated; values travel through %s markers.
    where, params = " WHERE tenant_id = %s", [tenant_id]
    if status is not None:
        where += " AND status = %s"
        params.append(status.value)
    if job_id is not None:
        where += " AND job_id = %s"
        params.append(job_id)
    return where, params
