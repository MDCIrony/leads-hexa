import secrets
from datetime import datetime
from uuid import UUID

from application.ports.output.mfa import MfaCryptoPort
from application.ports.output.security import PasswordHasherPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.primary_authentication import token_hash
from domain.agents.agent import Agent
from domain.mfa.agent_mfa import AgentMfa
from domain.value_objects.agent_role import AgentRole

MFA_RECOVERY_CODE_COUNT = 8


def new_recovery_codes() -> list[str]:
    return [secrets.token_hex(16) for _ in range(MFA_RECOVERY_CODE_COUNT)]


def store_recovery_codes(uow: UnitOfWorkPort, agent_id: UUID, codes: list[str], now: datetime) -> None:
    uow.mfa.replace_recovery_codes(agent_id, (token_hash(code) for code in codes), now)


def proves_password(hasher: PasswordHasherPort, agent: Agent, password: str) -> bool:
    return (
        agent.role != AgentRole.INTEGRATION
        and bool(agent.hashed_password)
        and hasher.verify(password, agent.hashed_password)
    )


def claim_factor(
    uow: UnitOfWorkPort, crypto: MfaCryptoPort, enrollment: AgentMfa, code: str, now: datetime
) -> bool:
    """A current TOTP code, claimed so it works once, or else an unused recovery code."""
    step = crypto.matching_step(crypto.decrypt(enrollment.secret_ciphertext), code, now)
    if step is not None:
        return uow.mfa.claim_totp_step(enrollment.agent_id, step)
    return uow.mfa.consume_recovery_code(enrollment.agent_id, token_hash(code), now)
