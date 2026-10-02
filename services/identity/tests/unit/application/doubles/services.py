"""Deterministic stand-ins for hashing, MFA crypto and the Kafka provisioner."""
from datetime import datetime
from uuid import UUID

from application.ports.output.messaging import MessagingCredentialProvisionerPort, MessagingProvisioningError
from application.ports.output.mfa import MfaCryptoPort
from application.ports.output.security import PasswordHasherPort

VALID_TOTP = "123456"


class FakePasswordHasher(PasswordHasherPort):
    """Keeps unit tests free of bcrypt's cost factor (~250 ms per call)."""

    _PREFIX = "hashed:"

    def hash(self, plain: str) -> str:
        return f"{self._PREFIX}{plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"{self._PREFIX}{plain}"


class FakeMfaCrypto(MfaCryptoPort):
    """VALID_TOTP always matches step 100, so a second use of it is a replay."""

    def generate_secret(self) -> str:
        return "pending-secret"

    def encrypt(self, secret: str) -> str:
        return f"encrypted:{secret}"

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext.removeprefix("encrypted:")

    def matching_step(self, secret: str, code: str, now: datetime) -> int | None:
        return 100 if secret == "pending-secret" and code == VALID_TOTP else None

    def provisioning_uri(self, secret: str, email: str) -> str:
        return f"otpauth://totp/Lead%20Router:{email}?secret={secret}"


class FakeMessagingCredentialProvisioner(MessagingCredentialProvisionerPort):
    """Records calls instead of touching a broker; fail=True simulates it unreachable."""

    def __init__(self, fail: bool = False) -> None:
        self.issued: list[UUID] = []
        self.revoked: list[UUID] = []
        self._fail = fail

    def issue_tenant_credential(self, tenant_id: UUID) -> str:
        if self._fail:
            raise MessagingProvisioningError("broker unreachable")
        self.issued.append(tenant_id)
        return f"kafka-secret-{tenant_id}"

    def revoke_tenant_credential(self, tenant_id: UUID) -> None:
        if self._fail:
            raise MessagingProvisioningError("broker unreachable")
        self.revoked.append(tenant_id)
