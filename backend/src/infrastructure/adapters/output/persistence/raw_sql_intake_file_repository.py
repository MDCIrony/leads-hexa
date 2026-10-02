from typing import Optional
from uuid import UUID

import psycopg

from application.dtos.commands import StoredIntakeFile
from application.ports.output.intake_file_repository_port import IntakeFileRepositoryPort


class RawSqlIntakeFileRepository(IntakeFileRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, job_id: UUID, tenant_id: UUID, filename: str, content: bytes) -> None:
        self.connection.execute(
            """
            INSERT INTO intake_files (job_id, tenant_id, filename, content, size_bytes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (job_id, tenant_id, filename, content, len(content)),
        )

    def get(self, job_id: UUID, tenant_id: UUID) -> Optional[StoredIntakeFile]:
        row = self.connection.execute(
            """
            SELECT job_id, tenant_id, filename, content, parsed_at
            FROM intake_files
            WHERE job_id = %s AND tenant_id = %s
            """,
            (job_id, tenant_id),
        ).fetchone()
        if row is None:
            return None
        return StoredIntakeFile(
            job_id=row["job_id"],
            tenant_id=row["tenant_id"],
            filename=row["filename"],
            content=bytes(row["content"]),
            parsed_at=row["parsed_at"],
        )

    def mark_parsed(self, job_id: UUID) -> None:
        self.connection.execute(
            "UPDATE intake_files SET parsed_at = now() WHERE job_id = %s", (job_id,)
        )
