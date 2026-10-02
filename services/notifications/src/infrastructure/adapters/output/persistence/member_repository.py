from uuid import UUID

import psycopg

from application.ports.output.member_repository import MemberRepositoryPort
from domain.members.member import Member


class PostgresMemberRepository(MemberRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def get(self, agent_id: UUID) -> Member | None:
        row = self.connection.execute("SELECT * FROM members WHERE agent_id = %s", (agent_id,)).fetchone()
        return Member(row["agent_id"], row["tenant_id"], row["role"], row["is_active"], row["version"]) if row else None

    def save(self, member: Member) -> None:
        self.connection.execute(
            """
            INSERT INTO members (agent_id, tenant_id, role, is_active, version)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (agent_id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                role = EXCLUDED.role,
                is_active = EXCLUDED.is_active,
                version = EXCLUDED.version
            """,
            (member.agent_id, member.tenant_id, member.role, member.is_active, member.version),
        )

    def active_manager_ids(self, tenant_id: UUID) -> list[UUID]:
        # Repeats Member.receives_organization_notices in SQL so the filter runs in the
        # database; the integration test keeps both in step.
        rows = self.connection.execute(
            "SELECT agent_id FROM members WHERE tenant_id = %s AND role = 'MANAGER' AND is_active ORDER BY agent_id",
            (tenant_id,),
        ).fetchall()
        return [row["agent_id"] for row in rows]
