"""In-memory session, challenge, MFA and social identity repositories."""
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from application.ports.output.mfa import AgentMfaRepositoryPort
from application.ports.output.sessions import AuthChallengeRepositoryPort, AuthSessionRepositoryPort
from application.ports.output.social import SocialIdentityRepositoryPort
from domain.mfa.agent_mfa import AgentMfa
from domain.sessions.auth_challenge import AuthChallenge
from domain.sessions.auth_session import AuthSession
from domain.social.social_identity import SocialIdentity


class InMemoryAuthSessionRepository(AuthSessionRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, AuthSession] = {}

    def save(self, session: AuthSession) -> None:
        self.items[session.token_hash] = session

    def get_active(self, token_hash: str, now: datetime) -> AuthSession | None:
        session = self.items.get(token_hash)
        return session if session and session.revoked_at is None and session.expires_at > now else None

    def revoke(self, token_hash: str, now: datetime) -> None:
        session = self.items.get(token_hash)
        if session and session.revoked_at is None:
            self.items[token_hash] = replace(session, revoked_at=now)

    def revoke_for_agent_except(self, agent_id: UUID, token_hash: str, now: datetime) -> None:
        for item_hash, session in list(self.items.items()):
            if session.agent_id == agent_id and item_hash != token_hash and session.revoked_at is None:
                self.items[item_hash] = replace(session, revoked_at=now)


class InMemoryAuthChallengeRepository(AuthChallengeRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, AuthChallenge] = {}

    def save(self, challenge: AuthChallenge) -> None:
        self.items[challenge.token_hash] = challenge

    def resolve_active(self, token_hash: str, now: datetime) -> AuthChallenge | None:
        challenge = self.items.get(token_hash)
        return challenge if challenge and challenge.consumed_at is None and challenge.expires_at > now else None

    def increment_attempts(self, token_hash: str, now: datetime) -> bool:
        challenge = self.resolve_active(token_hash, now)
        if not challenge:
            return False
        self.items[token_hash] = replace(challenge, attempts=challenge.attempts + 1)
        return True

    def reserve_attempt(self, token_hash: str, purpose: str, now: datetime, maximum: int) -> bool:
        challenge = self.resolve_active(token_hash, now)
        if not challenge or challenge.purpose != purpose or challenge.agent_id is None or challenge.attempts >= maximum:
            return False
        self.items[token_hash] = replace(challenge, attempts=challenge.attempts + 1)
        return True

    def consume(self, token_hash: str, now: datetime) -> bool:
        challenge = self.resolve_active(token_hash, now)
        if not challenge:
            return False
        self.items[token_hash] = replace(challenge, consumed_at=now)
        return True

    def consume_oauth(self, token_hash: str, provider: str, state_hash: str, now: datetime) -> AuthChallenge | None:
        challenge = self.resolve_active(token_hash, now)
        if not challenge or not challenge.matches_oauth(provider, state_hash):
            return None
        self.items[token_hash] = replace(challenge, consumed_at=now)
        return self.items[token_hash]

    def invalidate_active_for_agent(self, agent_id: UUID, purpose: str, now: datetime) -> AuthChallenge | None:
        active = [
            challenge for token_hash, challenge in self.items.items()
            if challenge.agent_id == agent_id and challenge.purpose == purpose and self.resolve_active(token_hash, now)
        ]
        for challenge in active:
            self.items[challenge.token_hash] = replace(challenge, consumed_at=now)
        return max(active, key=lambda challenge: challenge.attempts, default=None)


class InMemoryAgentMfaRepository(AgentMfaRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[UUID, AgentMfa] = {}
        self.recovery_codes: dict[tuple[UUID, str], datetime | None] = {}

    def get(self, agent_id: UUID) -> AgentMfa | None:
        return self.items.get(agent_id)

    def save_pending(self, enrollment: AgentMfa) -> None:
        self.items[enrollment.agent_id] = AgentMfa(enrollment.agent_id, enrollment.secret_ciphertext)

    def confirm(self, agent_id: UUID, step: int, now: datetime) -> bool:
        enrollment = self.items.get(agent_id)
        if not enrollment or enrollment.enabled_at is not None:
            return False
        self.items[agent_id] = AgentMfa(agent_id, enrollment.secret_ciphertext, now, step)
        return True

    def claim_totp_step(self, agent_id: UUID, step: int) -> bool:
        enrollment = self.items.get(agent_id)
        if not enrollment or enrollment.enabled_at is None or (
            enrollment.last_used_step is not None and enrollment.last_used_step >= step
        ):
            return False
        self.items[agent_id] = replace(enrollment, last_used_step=step)
        return True

    def replace_recovery_codes(self, agent_id: UUID, code_hashes, now: datetime) -> None:
        self.recovery_codes = {key: value for key, value in self.recovery_codes.items() if key[0] != agent_id}
        self.recovery_codes.update({(agent_id, code_hash): None for code_hash in code_hashes})

    def consume_recovery_code(self, agent_id: UUID, code_hash: str, now: datetime) -> bool:
        key = (agent_id, code_hash)
        if key not in self.recovery_codes or self.recovery_codes[key] is not None:
            return False
        self.recovery_codes[key] = now
        return True

    def delete(self, agent_id: UUID) -> None:
        self.items.pop(agent_id, None)
        self.recovery_codes = {key: value for key, value in self.recovery_codes.items() if key[0] != agent_id}


class InMemorySocialIdentityRepository(SocialIdentityRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[UUID, SocialIdentity] = {}

    def get_by_provider_subject(self, provider: str, provider_subject: str) -> SocialIdentity | None:
        return next(
            (i for i in self.items.values() if i.provider == provider and i.provider_subject == provider_subject),
            None,
        )

    def list_by_agent(self, agent_id: UUID) -> list[SocialIdentity]:
        return sorted((i for i in self.items.values() if i.agent_id == agent_id), key=lambda i: i.provider)

    def save(self, identity: SocialIdentity) -> bool:
        if self.get_by_provider_subject(identity.provider, identity.provider_subject) or any(
            item.agent_id == identity.agent_id and item.provider == identity.provider
            for item in self.items.values()
        ):
            return False
        self.items[identity.id] = identity
        return True

    def touch_last_login(self, identity_id: UUID, now: datetime) -> bool:
        identity = self.items.get(identity_id)
        if not identity:
            return False
        self.items[identity_id] = replace(identity, last_login_at=now)
        return True
