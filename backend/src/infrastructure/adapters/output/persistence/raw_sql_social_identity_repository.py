from datetime import datetime
from typing import Optional
from uuid import UUID

import psycopg

from application.ports.output.social_identity_repository_port import SocialIdentityRepositoryPort
from domain.entities.social_identity import SocialIdentity


class RawSqlSocialIdentityRepository(SocialIdentityRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def get_by_provider_subject(self, provider: str, provider_subject: str) -> Optional[SocialIdentity]:
        row = self.connection.execute(
            "SELECT id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at "
            "FROM social_identities WHERE provider = %s AND provider_subject = %s",
            (provider, provider_subject),
        ).fetchone()
        return SocialIdentity(**dict(row)) if row else None

    def list_by_agent(self, agent_id: UUID) -> list[SocialIdentity]:
        rows = self.connection.execute(
            "SELECT id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at "
            "FROM social_identities WHERE agent_id = %s ORDER BY provider",
            (agent_id,),
        ).fetchall()
        return [SocialIdentity(**dict(row)) for row in rows]

    def save(self, identity: SocialIdentity) -> bool:
        return self.connection.execute(
            "INSERT INTO social_identities (id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
            (identity.id, identity.agent_id, identity.provider, identity.provider_subject, identity.email_at_link, identity.created_at, identity.last_login_at),
        ).fetchone() is not None

    def touch_last_login(self, identity_id: UUID, now: datetime) -> bool:
        return self.connection.execute(
            "UPDATE social_identities SET last_login_at = %s WHERE id = %s RETURNING id",
            (now, identity_id),
        ).fetchone() is not None
