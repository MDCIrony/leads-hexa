from datetime import datetime
from typing import Optional

import psycopg

from application.ports.output.auth_challenge_repository_port import AuthChallengeRepositoryPort
from domain.entities.auth_challenge import AuthChallenge


class RawSqlAuthChallengeRepository(AuthChallengeRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, challenge: AuthChallenge) -> None:
        self.connection.execute(
            "INSERT INTO auth_challenges (token_hash, agent_id, purpose, attempts, expires_at, consumed_at, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (challenge.token_hash, challenge.agent_id, challenge.purpose, challenge.attempts, challenge.expires_at, challenge.consumed_at, challenge.created_at),
        )

    def resolve_active(self, token_hash: str, now: datetime) -> Optional[AuthChallenge]:
        row = self.connection.execute(
            "SELECT token_hash, agent_id, purpose, attempts, expires_at, consumed_at, created_at FROM auth_challenges WHERE token_hash = %s AND consumed_at IS NULL AND expires_at > %s",
            (token_hash, now),
        ).fetchone()
        return AuthChallenge(**dict(row)) if row else None

    def increment_attempts(self, token_hash: str, now: datetime) -> bool:
        return self.connection.execute(
            "UPDATE auth_challenges SET attempts = attempts + 1 WHERE token_hash = %s AND consumed_at IS NULL AND expires_at > %s",
            (token_hash, now),
        ).rowcount == 1

    def consume(self, token_hash: str, now: datetime) -> bool:
        return self.connection.execute(
            "UPDATE auth_challenges SET consumed_at = %s WHERE token_hash = %s AND consumed_at IS NULL AND expires_at > %s",
            (now, token_hash, now),
        ).rowcount == 1
