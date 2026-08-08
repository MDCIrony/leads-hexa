import uuid
from domain.entities import Lead, Agent, ScoringRule, WebhookConfig
from domain.value_objects import (
    LeadId,
    TenantId,
    AgentId,
    LeadStatus,
    Operator,
    WebhookEventType,
)
from domain.value_objects.enums import AgentRole

def test_lead_entity_lifecycle():
    lead = Lead.create(
        tenant_id=uuid.uuid4(),
        first_name="Maria",
        last_name="Gomez",
        email="mgomez@techcorp.com",
        company="TechCorp Inc",
        budget=15000,
        industry="Technology",
        custom_attributes={"employee_count": 150},
    )

    assert lead.status == LeadStatus.NEW
    assert int(lead.score) == 0

    lead.apply_score(45)
    assert int(lead.score) == 45

    lead.qualify(threshold_qualified=30, threshold_disqualified=0)
    assert lead.status == LeadStatus.QUALIFIED

    agent_id = AgentId()
    lead.assign_to_agent(agent_id)
    assert lead.status == LeadStatus.ASSIGNED
    assert lead.assigned_agent_id == agent_id

def test_agent_entity_creation():
    agent = Agent.create(
        name="Carlos Lopez",
        email="clopez@sales.com",
    )
    assert agent.is_active is True
    assert agent.name == "Carlos Lopez"
    assert isinstance(agent.id, AgentId)

    # Test agent_id passing str, UUID, AgentId
    raw_uuid = uuid.uuid4()
    str_uuid = str(raw_uuid)
    vo_agent_id = AgentId(raw_uuid)

    agent_from_str = Agent.create("A", "a@test.com", agent_id=str_uuid)
    assert agent_from_str.id.value == raw_uuid

    agent_from_uuid = Agent.create("B", "b@test.com", agent_id=raw_uuid)
    assert agent_from_uuid.id.value == raw_uuid

    agent_from_vo = Agent.create("C", "c@test.com", agent_id=vo_agent_id)
    assert agent_from_vo.id == vo_agent_id


def test_agent_create_defaults_role_to_agent_and_has_no_password_or_tenant():
    agent = Agent.create("A", "a@test.com")
    assert agent.role == AgentRole.AGENT
    assert agent.hashed_password is None
    assert agent.tenant_id is None


def test_agent_create_accepts_role_password_and_tenant():
    tenant_uuid = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    agent = Agent.create(
        "B",
        "b@test.com",
        role=AgentRole.MANAGER,
        hashed_password="$2b$hash",
        tenant_id=tenant_uuid,
    )
    assert agent.role == AgentRole.MANAGER
    assert agent.hashed_password == "$2b$hash"
    assert str(agent.tenant_id) == tenant_uuid


def test_agent_create_positional_call_still_works():
    # Guards against breaking the existing calling convention used elsewhere in the suite:
    # group_id is now the third positional slot that team used to occupy.
    group_id = uuid.uuid4()
    agent = Agent.create("C", "c@test.com", group_id, agent_id="11111111-1111-1111-1111-111111111111")
    assert str(agent.id) == "11111111-1111-1111-1111-111111111111"
    assert agent.role == AgentRole.AGENT
    assert agent.group_id.value == group_id


def test_scoring_rule_entity_creation():
    rule = ScoringRule.create(
        name="High Budget",
        field="budget",
        operator="GREATER_THAN",
        value=10000,
        score_delta=25,
        rule_id=str(uuid.uuid4()),
    )
    assert rule.score_delta == 25
    assert rule.operator == Operator.GREATER_THAN
    assert isinstance(rule.id, uuid.UUID)

def test_webhook_config_entity_creation():
    tenant_uuid = uuid.uuid4()
    webhook = WebhookConfig.create(
        tenant_id=str(tenant_uuid),
        event_type="LEAD_INGESTED",
        target_url="https://example.com/webhook",
        secret_token="secret123",
    )
    assert isinstance(webhook.tenant_id, TenantId)
    assert webhook.tenant_id.value == tenant_uuid
    assert webhook.event_type == WebhookEventType.LEAD_INGESTED
    assert webhook.target_url == "https://example.com/webhook"
    assert webhook.secret_token == "secret123"
    assert isinstance(webhook.id, uuid.UUID)


class TestAgentGroupMembership:
    def test_an_agent_starts_without_a_group(self):
        """Belonging to a group is a decision the manager makes later."""
        agent = Agent.create(name="Ana", email="ana@a.test")
        assert agent.group_id is None

    def test_an_agent_can_be_created_inside_a_group(self):
        group_id = uuid.uuid4()
        agent = Agent.create(name="Ana", email="ana@a.test", group_id=group_id)
        assert agent.group_id is not None
        assert agent.group_id.value == group_id

    def test_the_group_can_be_given_as_a_string(self):
        group_id = uuid.uuid4()
        agent = Agent.create(name="Ana", email="ana@a.test", group_id=str(group_id))
        assert agent.group_id.value == group_id


class TestLeadLifecycleFields:
    def test_the_new_statuses_exist(self):
        assert LeadStatus.UNASSIGNED.value == "UNASSIGNED"
        assert LeadStatus.DISCARDED.value == "DISCARDED"

    def test_a_fresh_lead_carries_no_assignment_trace(self):
        lead = Lead.create(
            tenant_id=uuid.uuid4(), first_name="Ana", last_name="Diaz",
            email="ana@x.test", company="C", budget=100, industry="tech",
        )
        assert lead.assigned_at is None
        assert lead.discard_reason is None
        assert lead.updated_at is not None


