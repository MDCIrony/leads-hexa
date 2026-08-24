from uuid import UUID

from application.ports.output.messaging_credential_provisioner_port import (
    MessagingCredentialProvisionerPort,
    MessagingProvisioningError,
)


class FakeMessagingCredentialProvisioner(MessagingCredentialProvisionerPort):
    """Records calls instead of touching a broker. fail=True simulates the
    broker being unreachable."""

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
