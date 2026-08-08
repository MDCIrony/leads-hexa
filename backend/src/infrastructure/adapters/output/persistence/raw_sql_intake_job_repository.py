from typing import List, Optional
from uuid import UUID

import psycopg

from application.ports.output.intake_job_repository_port import IntakeJobRepositoryPort
from domain.entities.intake_job import IntakeJob
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus
from domain.value_objects.intake_job_id import IntakeJobId
from domain.value_objects.lead_source_id import LeadSourceId
from domain.value_objects.tenant_id import TenantId


class RawSqlIntakeJobRepository(IntakeJobRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, job: IntakeJob) -> IntakeJob:
        self.connection.execute(
            """
            INSERT INTO intake_jobs (
                id, tenant_id, source_id, kind, status, total_items, succeeded, failed,
                created_at, completed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                total_items = EXCLUDED.total_items,
                succeeded = EXCLUDED.succeeded,
                failed = EXCLUDED.failed,
                completed_at = EXCLUDED.completed_at
            """,
            (
                job.id.value,
                job.tenant_id.value,
                job.source_id.value,
                job.kind.value,
                job.status.value,
                job.total_items,
                job.succeeded,
                job.failed,
                job.created_at,
                job.completed_at,
            ),
        )
        return job

    def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> Optional[IntakeJob]:
        row = self.connection.execute(
            "SELECT * FROM intake_jobs WHERE id = %s AND tenant_id = %s",
            (job_id, tenant_id),
        ).fetchone()
        return self._row_to_job(row) if row else None

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeJobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeJob]:
        if status is not None:
            rows = self.connection.execute(
                "SELECT * FROM intake_jobs WHERE tenant_id = %s AND status = %s "
                "ORDER BY created_at, id LIMIT %s OFFSET %s",
                (tenant_id, status.value, limit, offset),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM intake_jobs WHERE tenant_id = %s "
                "ORDER BY created_at, id LIMIT %s OFFSET %s",
                (tenant_id, limit, offset),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None) -> int:
        if status is not None:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count FROM intake_jobs WHERE tenant_id = %s AND status = %s",
                (tenant_id, status.value),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count FROM intake_jobs WHERE tenant_id = %s",
                (tenant_id,),
            ).fetchone()
        return row["count"]

    def _row_to_job(self, row) -> IntakeJob:
        # Bypasses IntakeJob.create(): that factory always mints a fresh id
        # and PENDING/zeroed counters for a *new* job, so rebuilding an
        # existing row goes through the dataclass constructor directly.
        return IntakeJob(
            id=IntakeJobId(row["id"]),
            tenant_id=TenantId(row["tenant_id"]),
            source_id=LeadSourceId(row["source_id"]),
            kind=IntakeJobKind(row["kind"]),
            status=IntakeJobStatus(row["status"]),
            total_items=row["total_items"],
            succeeded=row["succeeded"],
            failed=row["failed"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
