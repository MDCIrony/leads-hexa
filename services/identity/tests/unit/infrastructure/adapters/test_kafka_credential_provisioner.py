import uuid

import pytest
from confluent_kafka import KafkaException
from confluent_kafka.admin import AclOperation, AclPermissionType, ResourcePatternType, ResourceType

import infrastructure.adapters.output.messaging.kafka_credential_provisioner as kcp_module
from application.ports.output.messaging import MessagingProvisioningError
from infrastructure.adapters.output.messaging.kafka_credential_provisioner import KafkaCredentialProvisioner

_TENANT = uuid.uuid4()


class _ResolvedFuture:
    """Stands in for the concurrent.futures.Future the real AdminClient
    returns: .result() either returns None or raises, same as the real one
    once the broker responds."""

    def __init__(self, error: Exception = None):
        self._error = error

    def result(self):
        if self._error is not None:
            raise self._error


class _FakeAdminClient:
    """Stands in for confluent_kafka.admin.AdminClient: records what it was
    asked to alter/create/delete instead of touching a broker."""

    def __init__(self, conf):
        self.conf = conf
        self.scram_alterations = []
        self.acls_created = []
        self.acl_filters_deleted = []
        self.error: Exception = None

    def alter_user_scram_credentials(self, alterations, **kwargs):
        self.scram_alterations.extend(alterations)
        return {a.user: _ResolvedFuture(self.error) for a in alterations}

    def create_acls(self, acls, **kwargs):
        self.acls_created.extend(acls)
        return {acl: _ResolvedFuture(self.error) for acl in acls}

    def delete_acls(self, acl_binding_filters, **kwargs):
        self.acl_filters_deleted.extend(acl_binding_filters)
        return {f: _ResolvedFuture(self.error) for f in acl_binding_filters}


@pytest.fixture
def fake_admin(monkeypatch):
    """Patches the class, so the client the provisioner builds on first use is
    this recording one and no broker is ever touched."""
    client = _FakeAdminClient(None)

    def _factory(conf):
        client.conf = conf
        return client

    monkeypatch.setattr(kcp_module, "AdminClient", _factory)
    return KafkaCredentialProvisioner("kafka:9092"), client


def test_building_the_provisioner_does_not_reach_for_the_broker(monkeypatch):
    def _refuse(conf):
        raise AssertionError("AdminClient built at construction")

    monkeypatch.setattr(kcp_module, "AdminClient", _refuse)
    KafkaCredentialProvisioner("kafka:9092")


def test_issuing_upserts_the_scram_user_and_grants_the_three_acls(fake_admin):
    provisioner, admin = fake_admin

    secret = provisioner.issue_tenant_credential(_TENANT)

    assert isinstance(secret, str) and secret
    assert admin.conf == {"bootstrap.servers": "kafka:9092"}
    assert len(admin.scram_alterations) == 1
    assert admin.scram_alterations[0].user == f"tenant-{_TENANT}"

    assert len(admin.acls_created) == 3
    principal = f"User:tenant-{_TENANT}"
    topic_acls = [a for a in admin.acls_created if a.restype == ResourceType.TOPIC]
    group_acls = [a for a in admin.acls_created if a.restype == ResourceType.GROUP]

    assert {a.operation for a in topic_acls} == {AclOperation.READ, AclOperation.DESCRIBE}
    for acl in topic_acls:
        assert acl.name == f"leads.{_TENANT}"
        assert acl.resource_pattern_type == ResourcePatternType.LITERAL
        assert acl.principal == principal
        assert acl.permission_type == AclPermissionType.ALLOW

    assert len(group_acls) == 1
    # The principal itself: the rule a customer follows is the string they
    # already authenticate as, not the name of a tool we happen to ship.
    assert group_acls[0].name == f"tenant-{_TENANT}"
    assert group_acls[0].resource_pattern_type == ResourcePatternType.PREFIXED
    assert group_acls[0].operation == AclOperation.READ
    assert group_acls[0].principal == principal


def test_revoking_deletes_the_scram_user_and_the_matching_acl_filters(fake_admin):
    provisioner, admin = fake_admin

    provisioner.revoke_tenant_credential(_TENANT)

    assert len(admin.scram_alterations) == 1
    assert admin.scram_alterations[0].user == f"tenant-{_TENANT}"

    principal = f"User:tenant-{_TENANT}"
    assert len(admin.acl_filters_deleted) == 2
    topic_filter = next(f for f in admin.acl_filters_deleted if f.restype == ResourceType.TOPIC)
    group_filter = next(f for f in admin.acl_filters_deleted if f.restype == ResourceType.GROUP)
    assert topic_filter.name == f"leads.{_TENANT}"
    assert topic_filter.resource_pattern_type == ResourcePatternType.LITERAL
    assert topic_filter.principal == principal
    assert group_filter.name == f"tenant-{_TENANT}"
    assert group_filter.resource_pattern_type == ResourcePatternType.PREFIXED
    assert group_filter.principal == principal


def test_a_broker_failure_on_issue_is_wrapped_not_propagated_raw(fake_admin):
    provisioner, admin = fake_admin
    admin.error = KafkaException("broker unreachable")

    with pytest.raises(MessagingProvisioningError):
        provisioner.issue_tenant_credential(_TENANT)


def test_a_broker_failure_on_revoke_is_wrapped_not_propagated_raw(fake_admin):
    provisioner, admin = fake_admin
    admin.error = KafkaException("broker unreachable")

    with pytest.raises(MessagingProvisioningError):
        provisioner.revoke_tenant_credential(_TENANT)
