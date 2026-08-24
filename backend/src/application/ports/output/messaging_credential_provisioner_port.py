import abc
from uuid import UUID


def kafka_username(tenant_id: UUID) -> str:
    """The tenant's SCRAM username, also its ACL principal.

    Lives here, not in the adapter, so IssueIntegrationCredentialUseCase can
    report it without the application layer importing infrastructure
    (Guardián 4/4) — the adapter imports it back from this port instead of
    defining its own copy, keeping exactly one source of truth."""
    return f"tenant-{tenant_id}"


class MessagingProvisioningError(Exception):
    """Raised when the broker cannot take a credential or ACL change right
    now. Adapters translate their client library's own exceptions into this
    one, so the application layer never has to import a messaging client to
    handle the failure (Guardián 4/4)."""


class MessagingCredentialProvisionerPort(abc.ABC):
    """Issues and revokes the SCRAM credential and ACL that let one
    organization's own consumer read its own topic, and nothing else
    (ADR-0028)."""

    @abc.abstractmethod
    def issue_tenant_credential(self, tenant_id: UUID) -> str:
        """Create the tenant's SCRAM user if absent, or rotate its password if
        present, and (re)grant its ACL. Returns the plaintext password —
        the only place it is ever available outside Kafka's own SCRAM store,
        this codebase never persists it.

        Raises MessagingProvisioningError if the broker cannot be reached."""

    @abc.abstractmethod
    def revoke_tenant_credential(self, tenant_id: UUID) -> None:
        """Delete the tenant's SCRAM user and its ACL grants.

        Raises MessagingProvisioningError if the broker cannot be reached."""
