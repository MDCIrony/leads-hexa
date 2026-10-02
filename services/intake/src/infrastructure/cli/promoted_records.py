from collections.abc import Iterator
from datetime import datetime
from typing import NamedTuple
from uuid import UUID

from chassis.persistence import RawSqlDatabase


class PromotedRecord(NamedTuple):
    record_id: UUID
    tenant_id: UUID
    lead_id: UUID


def promoted_since(database: RawSqlDatabase, since: datetime, batch_size: int) -> Iterator[list[PromotedRecord]]:
    """PROMOTED records closed at or after `since`, in pages of `batch_size`.

    Keyset paging on (processed_at, id): an OFFSET would skip or repeat records
    if the worker promotes more while the walk is under way."""
    # The nil UUID sorts first, so the opening cursor includes records closed exactly at `since`.
    cursor: tuple[datetime, UUID] = (since, UUID(int=0))
    while True:
        with database.get_connection(autocommit=True) as conn:
            rows = conn.execute(
                """
                SELECT id, tenant_id, lead_id, processed_at FROM intake_records
                WHERE status = 'PROMOTED' AND (processed_at, id) > (%s, %s)
                ORDER BY processed_at, id
                LIMIT %s
                """,
                (*cursor, batch_size),
            ).fetchall()
        if not rows:
            return
        yield [PromotedRecord(row["id"], row["tenant_id"], row["lead_id"]) for row in rows]
        cursor = (rows[-1]["processed_at"], rows[-1]["id"])
