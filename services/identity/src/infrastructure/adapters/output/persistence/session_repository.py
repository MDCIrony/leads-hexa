from datetime import datetime
from uuid import UUID

import psycopg

from application.ports.output.sessions import AuthSessionRepositoryPort
from domain.sessions.auth_session import AuthSession


class PostgresAuthSessionRepository(AuthSessionRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, session: AuthSession) -> None:
        self.connection.execute(
            "INSERT INTO auth_sessions (token_hash, agent_id, created_at, expires_at, revoked_at)"
            " VALUES (%s, %s, %s, %s, %s)",
            (session.token_hash, session.agent_id, session.created_at, session.expires_at, session.revoked_at),
        )

    def get_active(self, token_hash: str, now: datetime) -> AuthSession | None:
        row = self.connection.execute(
            "SELECT token_hash, agent_id, created_at, expires_at, revoked_at FROM auth_sessions"
            " WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > %s",
            (token_hash, now),
        ).fetchone()
        return AuthSession(**row) if row else None

    def revoke(self, token_hash: str, now: datetime) -> None:
        self.connection.execute(
            "UPDATE auth_sessions SET revoked_at = %s WHERE token_hash = %s AND revoked_at IS NULL",
            (now, token_hash),
        )

    def revoke_for_agent_except(self, agent_id: UUID, token_hash: str, now: datetime) -> None:
        self.connection.execute(
            "UPDATE auth_sessions SET revoked_at = %s"
            " WHERE agent_id = %s AND token_hash <> %s AND revoked_at IS NULL",
            (now, agent_id, token_hash),
        )
