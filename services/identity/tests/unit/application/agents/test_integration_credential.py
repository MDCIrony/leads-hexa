import uuid

import pytest

from application.dtos.agents import IssueIntegrationCredentialCommand
from application.use_cases.agents.integration_credential import IssueIntegrationCredentialUseCase
from domain.exceptions import DomainException
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.services import FakeMessagingCredentialProvisioner, FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _subject(fail=False):
    uow = InMemoryUnitOfWork()
    tenant = uow.tenants.save(Tenant.create(name="Acme"))
    hasher = FakePasswordHasher()
    use_case = IssueIntegrationCredentialUseCase(
        uow=uow, password_hasher=hasher, messaging_provisioner=FakeMessagingCredentialProvisioner(fail=fail)
    )
    return uow, tenant, hasher, use_case


def test_first_call_creates_an_integration_agent_whose_api_key_verifies():
    _, tenant, hasher, use_case = _subject()

    result = use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

    assert result.agent.role == AgentRole.INTEGRATION
    assert result.agent.email == "integration@acme.invalid"
    agent_id, secret = result.api_key.split(".", 1)
    assert agent_id == str(result.agent.id)
    assert hasher.verify(secret, result.agent.hashed_password)
    assert result.kafka_username == f"tenant-{tenant.id.value}"
    assert result.kafka_password == f"kafka-secret-{tenant.id.value}"
    assert result.kafka_topic == f"leads.{tenant.id.value}"


def test_second_call_rotates_instead_of_creating_a_second_row():
    uow, tenant, hasher, use_case = _subject()

    first = use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))
    first.agent.is_active = False
    second = use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

    assert str(second.agent.id) == str(first.agent.id)
    assert second.agent.is_active is True
    assert uow.agents.count() == 1
    _, first_secret = first.api_key.split(".", 1)
    assert not hasher.verify(first_secret, second.agent.hashed_password)


def test_a_broker_failure_leaves_no_agent_row_behind():
    uow, tenant, _, use_case = _subject(fail=True)

    with pytest.raises(DomainException) as exc:
        use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

    assert exc.value.error_code == "MESSAGING_UNAVAILABLE"
    assert uow.agents.count() == 0
    assert uow.events() == []


def test_an_unknown_organization_is_tenant_not_found():
    *_, use_case = _subject()
    with pytest.raises(DomainException) as exc:
        use_case.execute(IssueIntegrationCredentialCommand(tenant_id=uuid.uuid4()))
    assert exc.value.error_code == "TENANT_NOT_FOUND"
