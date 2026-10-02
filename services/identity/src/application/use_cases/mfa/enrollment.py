from datetime import datetime, timezone

from application.dtos.auth import MfaSetupResult
from application.ports.input.mfa import MfaEnrollmentInputPort
from application.ports.output.mfa import MfaCryptoPort
from application.ports.output.security import PasswordHasherPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import token_hash
from application.use_cases.mfa.factors import (
    claim_factor,
    new_recovery_codes,
    proves_password,
    store_recovery_codes,
)
from domain.agents.agent import Agent
from domain.exceptions import InvalidCredentialsException
from domain.mfa.agent_mfa import AgentMfa


def _invalid_factor() -> InvalidCredentialsException:
    return InvalidCredentialsException("Invalid authentication factor")


class MfaEnrollmentUseCase(MfaEnrollmentInputPort):
    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort, crypto: MfaCryptoPort) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.crypto = crypto

    def setup(self, agent: Agent, password: str) -> MfaSetupResult:
        if not proves_password(self.password_hasher, agent, password):
            raise _invalid_factor()
        secret = self.crypto.generate_secret()
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if enrollment and enrollment.enabled_at is not None:
                raise _invalid_factor()
            self.uow.mfa.save_pending(AgentMfa(agent.id.value, self.crypto.encrypt(secret)))
        return MfaSetupResult(secret=secret, otpauth_uri=self.crypto.provisioning_uri(secret, agent.email))

    def confirm(self, agent: Agent, current_session_token: str, code: str) -> list[str]:
        now = datetime.now(timezone.utc)
        codes = new_recovery_codes()
        succeeded = False
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if enrollment and enrollment.enabled_at is None:
                step = self.crypto.matching_step(self.crypto.decrypt(enrollment.secret_ciphertext), code, now)
                if step is not None and self.uow.mfa.confirm(agent.id.value, step, now):
                    store_recovery_codes(self.uow, agent.id.value, codes, now)
                    # Sessions opened before MFA existed must not outlive it.
                    self.uow.sessions.revoke_for_agent_except(agent.id.value, token_hash(current_session_token), now)
                    succeeded = True
        if not succeeded:
            raise _invalid_factor()
        return codes

    def regenerate_recovery_codes(self, agent: Agent, password: str, code: str) -> list[str]:
        now = datetime.now(timezone.utc)
        codes = new_recovery_codes()
        succeeded = False
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if (
                proves_password(self.password_hasher, agent, password)
                and enrollment and enrollment.enabled_at
                and claim_factor(self.uow, self.crypto, enrollment, code, now)
            ):
                store_recovery_codes(self.uow, agent.id.value, codes, now)
                succeeded = True
        if not succeeded:
            raise _invalid_factor()
        return codes

    def disable(self, agent: Agent, current_session_token: str | None, password: str, code: str) -> None:
        now = datetime.now(timezone.utc)
        succeeded = False
        with self.uow:
            enrollment = self.uow.mfa.get(agent.id.value)
            if (
                current_session_token
                and proves_password(self.password_hasher, agent, password)
                and enrollment and enrollment.enabled_at
                and claim_factor(self.uow, self.crypto, enrollment, code, now)
            ):
                self.uow.mfa.delete(agent.id.value)
                self.uow.sessions.revoke_for_agent_except(agent.id.value, token_hash(current_session_token), now)
                succeeded = True
        if not succeeded:
            raise _invalid_factor()
