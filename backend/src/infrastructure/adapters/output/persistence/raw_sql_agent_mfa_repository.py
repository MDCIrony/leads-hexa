from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

import psycopg

from application.ports.output.agent_mfa_repository_port import AgentMfaRepositoryPort
from domain.entities.agent_mfa import AgentMfa


class RawSqlAgentMfaRepository(AgentMfaRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def get(self, agent_id: UUID) -> Optional[AgentMfa]:
        row = self.connection.execute(
            "SELECT agent_id, secret_ciphertext, enabled_at, last_used_step FROM agent_mfa WHERE agent_id = %s",
            (agent_id,),
        ).fetchone()
        return AgentMfa(**dict(row)) if row else None

    def save_pending(self, enrollment: AgentMfa) -> None:
        self.connection.execute(
            "INSERT INTO agent_mfa (agent_id, secret_ciphertext, enabled_at, last_used_step) VALUES (%s, %s, NULL, NULL) "
            "ON CONFLICT (agent_id) DO UPDATE SET secret_ciphertext = EXCLUDED.secret_ciphertext, enabled_at = NULL, last_used_step = NULL",
            (enrollment.agent_id, enrollment.secret_ciphertext),
        )

    def confirm(self, agent_id: UUID, step: int, now: datetime) -> bool:
        return self.connection.execute(
            "UPDATE agent_mfa SET enabled_at = %s, last_used_step = %s "
            "WHERE agent_id = %s AND enabled_at IS NULL",
            (now, step, agent_id),
        ).rowcount == 1

    def claim_totp_step(self, agent_id: UUID, step: int) -> bool:
        return self.connection.execute(
            "UPDATE agent_mfa SET last_used_step = %s WHERE agent_id = %s AND enabled_at IS NOT NULL "
            "AND (last_used_step IS NULL OR last_used_step < %s)",
            (step, agent_id, step),
        ).rowcount == 1

    def replace_recovery_codes(self, agent_id: UUID, code_hashes: Iterable[str], now: datetime) -> None:
        self.connection.execute("DELETE FROM mfa_recovery_codes WHERE agent_id = %s", (agent_id,))
        with self.connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO mfa_recovery_codes (agent_id, code_hash, created_at) VALUES (%s, %s, %s)",
                [(agent_id, code_hash, now) for code_hash in code_hashes],
            )

    def consume_recovery_code(self, agent_id: UUID, code_hash: str, now: datetime) -> bool:
        return self.connection.execute(
            "UPDATE mfa_recovery_codes SET used_at = %s WHERE agent_id = %s AND code_hash = %s AND used_at IS NULL",
            (now, agent_id, code_hash),
        ).rowcount == 1

    def delete(self, agent_id: UUID) -> None:
        self.connection.execute("DELETE FROM agent_mfa WHERE agent_id = %s", (agent_id,))
