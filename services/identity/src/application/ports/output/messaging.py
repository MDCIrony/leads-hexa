from abc import ABC, abstractmethod
from uuid import UUID


def kafka_username(tenant_id: UUID) -> str:
    """The tenant's SCRAM username and ACL principal. Here, not in the adapter, so the
    use case can report it without importing infrastructure; the adapter imports it back."""
    return f"tenant-{tenant_id}"


class MessagingProvisioningError(Exception):
    """The broker cannot take a credential or ACL change right now. Adapters translate
    their client's exceptions into this one, so the application never imports a client."""


class MessagingCredentialProvisionerPort(ABC):
    """Issues and revokes the SCRAM credential and ACL that let one organization's
    consumer read its own topic and nothing else (ADR-0028)."""

    @abstractmethod
    def issue_tenant_credential(self, tenant_id: UUID) -> str:
        """Create or rotate the tenant's SCRAM user and (re)grant its ACL. Returns the
        plaintext password, never persisted here. Raises MessagingProvisioningError."""

    @abstractmethod
    def revoke_tenant_credential(self, tenant_id: UUID) -> None:
        """Delete the tenant's SCRAM user and ACL grants. Raises MessagingProvisioningError."""
