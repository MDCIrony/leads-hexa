from dataclasses import dataclass
from uuid import UUID

from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.mfa_crypto_port import MfaCryptoPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from domain.entities.auth_session import AuthSession
from domain.entities.auth_challenge import AuthChallenge
from domain.entities.agent_mfa import AgentMfa
from domain.entities.agent import Agent
from domain.entities.agent import normalize_email
from domain.exceptions import InvalidCredentialsException, InvalidMfaFactorException
from domain.value_objects.enums import AgentRole


MFA_CHALLENGE_PURPOSE = "MFA_LOGIN"
MFA_CHALLENGE_MINUTES = 5
MFA_CHALLENGE_ATTEMPTS = 5
MFA_RECOVERY_CODE_COUNT = 8


@dataclass(frozen=True)
class LoginResult:
    status: str
    token: str


@dataclass(frozen=True)
class MfaSetupResult:
    secret: str
    otpauth_uri: str


class _LostMfaChallenge(Exception):
    pass


class LoginUseCase(LoginInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
        session_hours: int = 8,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.session_hours = session_hours

    def execute(self, email: str, password: str) -> LoginResult:
        now = datetime.now(timezone.utc)
        with self.uow:
            agent = self.uow.agents.get_by_email(normalize_email(email))
            # One exception for every failure path: a caller must not be able to
            # tell an unknown account from a wrong password. INTEGRATION is
            # excluded here too: it is a machine principal whose only door in is
            # POST /agents/integration-credential, never a browser session.
            if (
                not agent
                or not agent.is_active
                or not agent.hashed_password
                or agent.role == AgentRole.INTEGRATION
                or not self.password_hasher.verify(password, agent.hashed_password)
            ):
                raise InvalidCredentialsException()

            enrollment = self.uow.mfa.get(agent.id.value)
            token = secrets.token_urlsafe(32)
            previous_challenge = self.uow.challenges.invalidate_active_for_agent(
                agent.id.value, MFA_CHALLENGE_PURPOSE, now
            )
            if enrollment and enrollment.enabled_at is not None:
                self.uow.challenges.save(AuthChallenge(
                    token_hash=sha256(token.encode()).hexdigest(), agent_id=agent.id.value,
                    purpose=MFA_CHALLENGE_PURPOSE,
                    attempts=previous_challenge.attempts if previous_challenge else 0,
                    expires_at=previous_challenge.expires_at if previous_challenge else now + timedelta(minutes=MFA_CHALLENGE_MINUTES),
                    consumed_at=None, created_at=now,
                ))
                return LoginResult(status="MFA_REQUIRED", token=token)
            self.uow.sessions.save(AuthSession(
                token_hash=sha256(token.encode()).hexdigest(),
                agent_id=agent.id.value,
                created_at=now,
                expires_at=now + timedelta(hours=self.session_hours),
            ))
            return LoginResult(status="AUTHENTICATED", token=token)


class MfaUseCase:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
        crypto: MfaCryptoPort,
        session_hours: int = 8,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.crypto = crypto
        self.session_hours = session_hours

    @staticmethod
    def _human(agent: Agent) -> bool:
        return agent.role != AgentRole.INTEGRATION

    @staticmethod
    def _recovery_codes() -> list[str]:
        return [secrets.token_hex(16) for _ in range(MFA_RECOVERY_CODE_COUNT)]

    @staticmethod
    def _hash(code: str) -> str:
        return sha256(code.encode()).hexdigest()

    def setup(self, agent: Agent, password: str) -> MfaSetupResult:
        if not self._human(agent) or not agent.hashed_password or not self.password_hasher.verify(password, agent.hashed_password):
            raise InvalidCredentialsException("Invalid authentication factor")
        secret = self.crypto.generate_secret()
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if enrollment and enrollment.enabled_at is not None:
                raise InvalidCredentialsException("Invalid authentication factor")
            self.uow.mfa.save_pending(AgentMfa(agent.id.value, self.crypto.encrypt(secret)))
        return MfaSetupResult(secret=secret, otpauth_uri=self.crypto.provisioning_uri(secret, agent.email))

    def confirm(self, agent: Agent, current_session_token: str, code: str) -> list[str]:
        now = datetime.now(timezone.utc)
        codes = self._recovery_codes()
        succeeded = False
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if enrollment and enrollment.enabled_at is None:
                step = self.crypto.matching_step(self.crypto.decrypt(enrollment.secret_ciphertext), code, now)
                if step is not None and self.uow.mfa.confirm(agent.id.value, step, now):
                    self.uow.mfa.replace_recovery_codes(agent.id.value, (self._hash(item) for item in codes), now)
                    self.uow.sessions.revoke_for_agent_except(
                        agent.id.value, self._hash(current_session_token), now
                    )
                    succeeded = True
        if not succeeded:
            raise InvalidCredentialsException("Invalid authentication factor")
        return codes

    def verify_login(self, challenge_token: str | None, code: str) -> LoginResult:
        now = datetime.now(timezone.utc)
        if not challenge_token:
            raise InvalidMfaFactorException(terminal=True)
        challenge_hash = self._hash(challenge_token)
        session_token = secrets.token_urlsafe(32)
        succeeded = False
        terminal = True
        try:
            with self.uow:
                if self.uow.challenges.reserve_attempt(
                    challenge_hash, MFA_CHALLENGE_PURPOSE, now, MFA_CHALLENGE_ATTEMPTS
                ):
                    challenge = self.uow.challenges.resolve_active(challenge_hash, now)
                    if challenge and challenge.agent_id:
                        terminal = challenge.attempts >= MFA_CHALLENGE_ATTEMPTS
                        agent = self.uow.agents.get_by_id(challenge.agent_id)
                        enrollment = self.uow.mfa.get(challenge.agent_id)
                        if agent and agent.is_active and self._human(agent) and enrollment and enrollment.enabled_at:
                            step = self.crypto.matching_step(self.crypto.decrypt(enrollment.secret_ciphertext), code, now)
                            factor_claimed = (
                                self.uow.mfa.claim_totp_step(challenge.agent_id, step)
                                if step is not None
                                else self.uow.mfa.consume_recovery_code(challenge.agent_id, self._hash(code), now)
                            )
                            if factor_claimed:
                                if not self.uow.challenges.consume(challenge_hash, now):
                                    raise _LostMfaChallenge()
                                self.uow.sessions.save(AuthSession(
                                    token_hash=self._hash(session_token), agent_id=challenge.agent_id,
                                    created_at=now, expires_at=now + timedelta(hours=self.session_hours),
                                ))
                                succeeded = True
        except _LostMfaChallenge:
            raise InvalidMfaFactorException(terminal=True) from None
        if not succeeded:
            raise InvalidMfaFactorException(terminal=terminal)
        return LoginResult(status="AUTHENTICATED", token=session_token)

    def regenerate_recovery_codes(self, agent: Agent, password: str, code: str) -> list[str]:
        now = datetime.now(timezone.utc)
        codes = self._recovery_codes()
        succeeded = False
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if (
                self._human(agent)
                and agent.hashed_password
                and self.password_hasher.verify(password, agent.hashed_password)
                and enrollment
                and enrollment.enabled_at
            ):
                step = self.crypto.matching_step(self.crypto.decrypt(enrollment.secret_ciphertext), code, now)
                factor_claimed = (
                    self.uow.mfa.claim_totp_step(agent.id.value, step)
                    if step is not None
                    else self.uow.mfa.consume_recovery_code(agent.id.value, self._hash(code), now)
                )
                if factor_claimed:
                    self.uow.mfa.replace_recovery_codes(agent.id.value, (self._hash(item) for item in codes), now)
                    succeeded = True
        if not succeeded:
            raise InvalidCredentialsException("Invalid authentication factor")
        return codes

    def disable(self, agent: Agent, current_session_token: str | None, password: str, code: str) -> None:
        now = datetime.now(timezone.utc)
        succeeded = False
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if (
                current_session_token
                and self._human(agent)
                and agent.hashed_password
                and self.password_hasher.verify(password, agent.hashed_password)
                and enrollment
                and enrollment.enabled_at
            ):
                step = self.crypto.matching_step(self.crypto.decrypt(enrollment.secret_ciphertext), code, now)
                factor_claimed = (
                    self.uow.mfa.claim_totp_step(agent.id.value, step)
                    if step is not None
                    else self.uow.mfa.consume_recovery_code(agent.id.value, self._hash(code), now)
                )
                if factor_claimed:
                    self.uow.mfa.delete(agent.id.value)
                    self.uow.sessions.revoke_for_agent_except(agent.id.value, self._hash(current_session_token), now)
                    succeeded = True
        if not succeeded:
            raise InvalidCredentialsException("Invalid authentication factor")
