from datetime import datetime
from uuid import UUID

import psycopg

from application.ports.output.sessions import AuthChallengeRepositoryPort
from domain.sessions.auth_challenge import AuthChallenge

_COLUMNS = (
    "token_hash, agent_id, purpose, attempts, expires_at, consumed_at, created_at,"
    " provider, state_hash, pkce_verifier, return_path"
)
# Every single-use guarantee below is one conditional UPDATE: the row lock it takes
# is what makes two racing transactions split one True and one False.
_LIVE = "consumed_at IS NULL AND expires_at > %s"


class PostgresAuthChallengeRepository(AuthChallengeRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, challenge: AuthChallenge) -> None:
        self.connection.execute(
            "INSERT INTO auth_challenges (" + _COLUMNS + ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                challenge.token_hash, challenge.agent_id, challenge.purpose, challenge.attempts,
                challenge.expires_at, challenge.consumed_at, challenge.created_at, challenge.provider,
                challenge.state_hash, challenge.pkce_verifier, challenge.return_path,
            ),
        )

    def resolve_active(self, token_hash: str, now: datetime) -> AuthChallenge | None:
        row = self.connection.execute(
            "SELECT " + _COLUMNS + " FROM auth_challenges WHERE token_hash = %s AND " + _LIVE,
            (token_hash, now),
        ).fetchone()
        return AuthChallenge(**row) if row else None

    def increment_attempts(self, token_hash: str, now: datetime) -> bool:
        return self.connection.execute(
            "UPDATE auth_challenges SET attempts = attempts + 1 WHERE token_hash = %s AND " + _LIVE,
            (token_hash, now),
        ).rowcount == 1

    def reserve_attempt(self, token_hash: str, purpose: str, now: datetime, maximum: int) -> bool:
        return self.connection.execute(
            "UPDATE auth_challenges SET attempts = attempts + 1"
            " WHERE token_hash = %s AND purpose = %s AND agent_id IS NOT NULL AND " + _LIVE
            + " AND attempts < %s",
            (token_hash, purpose, now, maximum),
        ).rowcount == 1

    def consume(self, token_hash: str, now: datetime) -> bool:
        return self.connection.execute(
            "UPDATE auth_challenges SET consumed_at = %s WHERE token_hash = %s AND " + _LIVE,
            (now, token_hash, now),
        ).rowcount == 1

    def consume_oauth(self, token_hash: str, provider: str, state_hash: str, now: datetime) -> AuthChallenge | None:
        row = self.connection.execute(
            "UPDATE auth_challenges SET consumed_at = %s"
            " WHERE token_hash = %s AND purpose = 'OAUTH_LOGIN' AND provider = %s AND state_hash = %s AND "
            + _LIVE + " RETURNING " + _COLUMNS,
            (now, token_hash, provider, state_hash, now),
        ).fetchone()
        challenge = AuthChallenge(**row) if row else None
        # The SQL equality already matched; this repeats it in constant time.
        return challenge if challenge and challenge.matches_oauth(provider, state_hash) else None

    def invalidate_active_for_agent(self, agent_id: UUID, purpose: str, now: datetime) -> AuthChallenge | None:
        rows = self.connection.execute(
            "UPDATE auth_challenges SET consumed_at = %s WHERE agent_id = %s AND purpose = %s AND "
            + _LIVE + " RETURNING " + _COLUMNS,
            (now, agent_id, purpose, now),
        ).fetchall()
        return max((AuthChallenge(**row) for row in rows), key=lambda challenge: challenge.attempts, default=None)
