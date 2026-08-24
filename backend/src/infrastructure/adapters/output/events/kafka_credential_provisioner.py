import secrets
from uuid import UUID

from confluent_kafka import KafkaException
from confluent_kafka.admin import (
    AclBinding,
    AclBindingFilter,
    AclOperation,
    AclPermissionType,
    AdminClient,
    ResourcePatternType,
    ResourceType,
    ScramCredentialInfo,
    ScramMechanism,
    UserScramCredentialDeletion,
    UserScramCredentialUpsertion,
)

from application.ports.output.messaging_credential_provisioner_port import (
    MessagingCredentialProvisionerPort,
    MessagingProvisioningError,
    kafka_username,
)


def consumer_group_prefix(tenant_id: UUID) -> str:
    """The prefix every consumer group of this tenant must start with.

    Its own principal, so the rule a customer has to follow is the same
    string they already authenticate as. Naming it after a tool we ship
    would mean a real client using their own group id — which is what a
    real client does — could not consume at all."""
    return kafka_username(tenant_id)


class KafkaCredentialProvisioner(MessagingCredentialProvisionerPort):
    """Talks to the broker over its internal, unauthenticated listener — the
    same one KafkaOutboundDispatcher already uses — where User:ANONYMOUS is a
    Kafka super.user (ADR-0028), so this adapter needs no credential of its
    own to manage everyone else's."""

    def __init__(self, bootstrap_servers: str, request_timeout_seconds: float = 10.0) -> None:
        self._admin = AdminClient({"bootstrap.servers": bootstrap_servers})
        self._timeout = request_timeout_seconds

    def issue_tenant_credential(self, tenant_id: UUID) -> str:
        username = kafka_username(tenant_id)
        secret = secrets.token_urlsafe(24)
        upsertion = UserScramCredentialUpsertion(
            user=username,
            scram_credential_info=ScramCredentialInfo(
                mechanism=ScramMechanism.SCRAM_SHA_256, iterations=8192,
            ),
            password=secret.encode(),
        )
        topic = f"leads.{tenant_id}"
        principal = f"User:{username}"
        acls = [
            AclBinding(ResourceType.TOPIC, topic, ResourcePatternType.LITERAL,
                       principal, "*", AclOperation.READ, AclPermissionType.ALLOW),
            AclBinding(ResourceType.TOPIC, topic, ResourcePatternType.LITERAL,
                       principal, "*", AclOperation.DESCRIBE, AclPermissionType.ALLOW),
            AclBinding(ResourceType.GROUP, consumer_group_prefix(tenant_id), ResourcePatternType.PREFIXED,
                       principal, "*", AclOperation.READ, AclPermissionType.ALLOW),
        ]
        try:
            self._admin.alter_user_scram_credentials([upsertion], request_timeout=self._timeout)[username].result()
            for binding, future in self._admin.create_acls(acls, request_timeout=self._timeout).items():
                future.result()
        except KafkaException as error:
            raise MessagingProvisioningError(f"Could not provision Kafka credential for {tenant_id}") from error
        return secret

    def revoke_tenant_credential(self, tenant_id: UUID) -> None:
        username = kafka_username(tenant_id)
        principal = f"User:{username}"
        deletion = UserScramCredentialDeletion(user=username, mechanism=ScramMechanism.SCRAM_SHA_256)
        filters = [
            AclBindingFilter(ResourceType.TOPIC, f"leads.{tenant_id}", ResourcePatternType.LITERAL,
                              principal, "*", AclOperation.ANY, AclPermissionType.ANY),
            AclBindingFilter(ResourceType.GROUP, consumer_group_prefix(tenant_id), ResourcePatternType.PREFIXED,
                              principal, "*", AclOperation.ANY, AclPermissionType.ANY),
        ]
        try:
            self._admin.alter_user_scram_credentials([deletion], request_timeout=self._timeout)[username].result()
            for binding, future in self._admin.delete_acls(filters, request_timeout=self._timeout).items():
                future.result()
        except KafkaException as error:
            raise MessagingProvisioningError(f"Could not revoke Kafka credential for {tenant_id}") from error
