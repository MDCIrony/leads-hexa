from typing import Any, List, Optional
from uuid import UUID

import psycopg

from application.ports.output.jobs import IntakeJobRepositoryPort
from domain.jobs.intake_job import IntakeJob
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus
from domain.value_objects.intake_job_id import IntakeJobId
from domain.value_objects.lead_source_id import LeadSourceId
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.correlation import current_correlation_id


class PostgresIntakeJobRepository(IntakeJobRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, job: IntakeJob) -> IntakeJob:
        self.connection.execute(
            """
            INSERT INTO intake_jobs (
                id, tenant_id, source_id, kind, status, total_items, succeeded, failed,
                created_at, completed_at, correlation_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            -- correlation_id is left out of the UPDATE: it names the request that
            -- created the job, not the worker that later advances it.
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
                current_correlation_id(),
            ),
        )
        return job

    def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> Optional[IntakeJob]:
        row = self.connection.execute(
            "SELECT * FROM intake_jobs WHERE id = %s AND tenant_id = %s", (job_id, tenant_id),
        ).fetchone()
        return _to_job(row) if row else None

    def list_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None, limit: int = 100, offset: int = 0,
    ) -> List[IntakeJob]:
        where, params = _filter(tenant_id, status)
        rows = self.connection.execute(
            "SELECT * FROM intake_jobs" + where + " ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
            [*params, limit, offset],
        ).fetchall()
        return [_to_job(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None) -> int:
        where, params = _filter(tenant_id, status)
        return self.connection.execute(
            "SELECT COUNT(*) AS count FROM intake_jobs" + where, params,
        ).fetchone()["count"]

    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        return self.connection.execute(
            "SELECT COUNT(*) AS count FROM intake_jobs WHERE tenant_id = %s AND source_id = %s",
            (tenant_id, source_id),
        ).fetchone()["count"]


def _filter(tenant_id: UUID, status: Optional[IntakeJobStatus]) -> tuple[str, List[Any]]:
    # Only fixed clauses are concatenated; every value travels through a %s marker.
    if status is None:
        return " WHERE tenant_id = %s", [tenant_id]
    return " WHERE tenant_id = %s AND status = %s", [tenant_id, status.value]


def _to_job(row) -> IntakeJob:
    # Not IntakeJob.create(): that factory mints a fresh id and PENDING/zeroed
    # counters for a new job, and this rebuilds an existing row.
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
