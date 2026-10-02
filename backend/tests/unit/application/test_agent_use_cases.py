import uuid
import pytest
from application.dtos.queries import GetAgentQuery
from application.dtos.commands import CreateAgentCommand, IssueIntegrationCredentialCommand, UpdateAgentCommand
from application.use_cases.agent_use_cases import (
    CreateAgentUseCase,
    DeactivateAgentUseCase,
    GetAgentUseCase,
    IssueIntegrationCredentialUseCase,
    UpdateAgentUseCase,
)
from domain.entities.agent import Agent
from domain.entities.sales_group import SalesGroup
from domain.entities.tenant import Tenant
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole
from domain.exceptions import AgentNotFoundException, DomainException
from tests.unit.mocks.fake_messaging_credential_provisioner import FakeMessagingCredentialProvisioner
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository


def _uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        InMemoryAgentRepository(),
        groups=InMemorySalesGroupRepository(),
    )


def test_get_agent_use_case_raises_when_agent_missing():
    uow = _uow()
    use_case = GetAgentUseCase(uow=uow)

    with pytest.raises(AgentNotFoundException) as exc_info:
        use_case.execute(GetAgentQuery(tenant_id=uuid.uuid4(), agent_id=uuid.uuid4()))

    assert exc_info.value.error_code == "AGENT_NOT_FOUND"


def test_create_agent_hashes_the_password_and_stores_role_and_tenant():
    uow = _uow()
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
    command = CreateAgentCommand(
        name="Jane",
        email="jane@test.com",
        password="plain-password",
        role="MANAGER",
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
    )
    saved = use_case.execute(command)
    assert saved.role == AgentRole.MANAGER
    assert str(saved.tenant_id) == "11111111-1111-1111-1111-111111111111"
    assert saved.hashed_password == "hashed:plain-password"


def test_create_agent_defaults_role_to_agent_and_tenant_to_none():
    uow = _uow()
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
    command = CreateAgentCommand(name="Bob", email="bob@test.com", password="x")
    saved = use_case.execute(command)
    assert saved.role == AgentRole.AGENT
    assert saved.tenant_id is None


def test_create_agent_normalizes_email_and_rejects_its_normalized_duplicate():
    uow = _uow()
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())

    saved = use_case.execute(CreateAgentCommand(name="Jane", email="  Jane@Example.Test ", password="x"))

    assert saved.email == "jane@example.test"
    with pytest.raises(DomainException) as exc_info:
        use_case.execute(CreateAgentCommand(name="Other", email="JANE@example.test", password="x"))
    assert exc_info.value.error_code == "EMAIL_ALREADY_EXISTS"


class TestUpdateAgent:
    def test_moves_an_agent_to_another_group_of_the_same_organization(self):
        uow = _uow()
        tenant = uuid.uuid4()
        origin = uow.groups.save(SalesGroup.create(tenant_id=tenant, name="Norte"))
        destination = uow.groups.save(SalesGroup.create(tenant_id=tenant, name="Sur"))
        agent = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            CreateAgentCommand(
                name="Ana",
                email="ana@acme.test",
                password="x",
                group_id=origin.id.value,
                tenant_id=tenant,
            )
        )

        updated = UpdateAgentUseCase(uow=uow).execute(
            UpdateAgentCommand(
                tenant_id=tenant, agent_id=agent.id.value, group_id=destination.id.value
            )
        )

        assert updated.group_id.value == destination.id.value

    def test_moving_an_agent_to_a_group_of_another_organization_is_rejected(self):
        uow = _uow()
        tenant, other_tenant = uuid.uuid4(), uuid.uuid4()
        foreign_group = uow.groups.save(SalesGroup.create(tenant_id=other_tenant, name="Ajeno"))
        agent = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            CreateAgentCommand(name="Ana", email="ana@acme.test", password="x", tenant_id=tenant)
        )

        with pytest.raises(DomainException) as exc:
            UpdateAgentUseCase(uow=uow).execute(
                UpdateAgentCommand(
                    tenant_id=tenant, agent_id=agent.id.value, group_id=foreign_group.id.value
                )
            )
        assert exc.value.error_code == "GROUP_NOT_FOUND"


class TestDeactivateAgent:
    def test_deactivating_excludes_the_agent_from_candidates_without_erasing_it(self):
        uow = _uow()
        tenant = uuid.uuid4()
        agent = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            CreateAgentCommand(name="Ana", email="ana@acme.test", password="x", tenant_id=tenant)
        )

        DeactivateAgentUseCase(uow=uow, messaging_provisioner=FakeMessagingCredentialProvisioner()).execute(
            GetAgentQuery(tenant_id=tenant, agent_id=agent.id.value)
        )

        assert agent.id.value not in {a.id.value for a in uow.agents.get_available_agents(tenant)}
        # The record itself survives: an agent's history must stay readable.
        survivor = uow.agents.get_by_id(agent.id.value)
        assert survivor is not None
        assert survivor.is_active is False

    def test_deactivating_a_regular_agent_does_not_touch_the_broker(self):
        uow = _uow()
        tenant = uuid.uuid4()
        agent = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            CreateAgentCommand(name="Ana", email="ana2@acme.test", password="x", tenant_id=tenant)
        )
        provisioner = FakeMessagingCredentialProvisioner()

        DeactivateAgentUseCase(uow=uow, messaging_provisioner=provisioner).execute(
            GetAgentQuery(tenant_id=tenant, agent_id=agent.id.value)
        )

        assert provisioner.revoked == []

    def test_deactivating_an_integration_credential_revokes_its_kafka_credential(self):
        uow = _uow()
        tenant = uuid.uuid4()
        agent = uow.agents.save(
            Agent.create(
                "Integración", "integration@acme.invalid", role=AgentRole.INTEGRATION, tenant_id=tenant
            )
        )
        provisioner = FakeMessagingCredentialProvisioner()

        DeactivateAgentUseCase(uow=uow, messaging_provisioner=provisioner).execute(
            GetAgentQuery(tenant_id=tenant, agent_id=agent.id.value)
        )

        assert provisioner.revoked == [tenant]


class TestIssueIntegrationCredential:
    def _uow_with_tenant(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme"))
        return uow, tenant

    def test_first_call_creates_an_integration_agent_whose_api_key_verifies(self):
        uow, tenant = self._uow_with_tenant()
        hasher = FakePasswordHasher()
        use_case = IssueIntegrationCredentialUseCase(
            uow=uow, password_hasher=hasher, messaging_provisioner=FakeMessagingCredentialProvisioner()
        )

        result = use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

        assert result.agent.role == AgentRole.INTEGRATION
        agent_id_str, secret = result.api_key.split(".", 1)
        assert agent_id_str == str(result.agent.id)
        assert hasher.verify(secret, result.agent.hashed_password)

    def test_second_call_rotates_instead_of_creating_a_second_row(self):
        uow, tenant = self._uow_with_tenant()
        hasher = FakePasswordHasher()
        use_case = IssueIntegrationCredentialUseCase(
            uow=uow, password_hasher=hasher, messaging_provisioner=FakeMessagingCredentialProvisioner()
        )

        first = use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))
        second = use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

        assert str(second.agent.id) == str(first.agent.id)
        assert uow.agents.count() == 1
        _, first_secret = first.api_key.split(".", 1)
        assert not hasher.verify(first_secret, second.agent.hashed_password)

    def test_a_broker_failure_leaves_no_agent_row_behind(self):
        uow, tenant = self._uow_with_tenant()
        use_case = IssueIntegrationCredentialUseCase(
            uow=uow,
            password_hasher=FakePasswordHasher(),
            messaging_provisioner=FakeMessagingCredentialProvisioner(fail=True),
        )

        with pytest.raises(DomainException) as exc:
            use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

        assert exc.value.error_code == "MESSAGING_UNAVAILABLE"
        assert uow.agents.count() == 0


def test_authorization_policy_rejects_integration_the_same_way_it_rejects_admin():
    manager = Agent.create("M", "m@acme.test", role=AgentRole.MANAGER, tenant_id=uuid.uuid4())
    assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.INTEGRATION) is False


def _agent_states(uow: InMemoryUnitOfWork):
    # Every row written, not only the eligible ones: list_unpublished hands out
    # a single row per key at a time, and these tests assert the whole history.
    entries = sorted(
        (e for e in uow.outbox._entries.values() if e.channel == "internal"),
        key=lambda e: e.occurred_on,
    )
    assert {e.event_type for e in entries} <= {"AgentState"}
    return [e.payload for e in entries]


class TestAgentStateEvents:
    def test_creating_records_the_new_agent(self):
        uow = _uow()
        saved = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(CreateAgentCommand(
            name="Jane", email="jane@test.com", password="plain-password", role="AGENT",
            tenant_id=uuid.uuid4(),
        ))

        states = _agent_states(uow)
        assert [s["agent_id"] for s in states] == [str(saved.id)]
        assert states[0]["version"] == 1
        assert "email" not in states[0] and "hashed_password" not in states[0]

    def test_deactivating_records_an_inactive_state_with_a_higher_version(self):
        uow = _uow()
        tenant = uuid.uuid4()
        agent = uow.agents.save(Agent.create("Ana", "ana@acme.test", tenant_id=tenant))
        before = agent.version

        DeactivateAgentUseCase(uow=uow, messaging_provisioner=FakeMessagingCredentialProvisioner()).execute(
            GetAgentQuery(tenant_id=tenant, agent_id=agent.id.value)
        )

        states = _agent_states(uow)
        assert len(states) == 1
        assert states[0]["is_active"] is False
        assert states[0]["version"] > before

    def test_updating_records_the_new_state(self):
        uow = _uow()
        tenant = uuid.uuid4()
        agent = uow.agents.save(Agent.create("Ana", "ana@acme.test", tenant_id=tenant))

        UpdateAgentUseCase(uow=uow).execute(
            UpdateAgentCommand(tenant_id=tenant, agent_id=agent.id.value, name="Ana María")
        )

        states = _agent_states(uow)
        assert [(s["name"], s["version"]) for s in states] == [("Ana María", 2)]

    def test_issuing_and_rotating_an_integration_credential_record_each_write(self):
        uow = _uow()
        tenant = uow.tenants.save(Tenant.create(name="Acme"))
        use_case = IssueIntegrationCredentialUseCase(
            uow=uow, password_hasher=FakePasswordHasher(),
            messaging_provisioner=FakeMessagingCredentialProvisioner(),
        )

        use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))
        use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

        states = _agent_states(uow)
        assert [(s["role"], s["version"]) for s in states] == [("INTEGRATION", 1), ("INTEGRATION", 2)]
