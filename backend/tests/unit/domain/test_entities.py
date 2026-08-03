import uuid
from domain.entities import Lead, Agent, ScoringRule, RoutingRule, WebhookConfig
from domain.value_objects import (
    LeadId,
    TenantId,
    AgentId,
    LeadStatus,
    Operator,
    AssignmentStrategy,
    WebhookEventType,
)

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
        team="Enterprise Sales",
        active_leads_count=2,
    )
    assert agent.is_active is True
    assert agent.active_leads_count == 2
    assert agent.name == "Carlos Lopez"
    assert isinstance(agent.id, AgentId)

    # Test agent_id passing str, UUID, AgentId
    raw_uuid = uuid.uuid4()
    str_uuid = str(raw_uuid)
    vo_agent_id = AgentId(raw_uuid)

    agent_from_str = Agent.create("A", "a@test.com", "Team", agent_id=str_uuid)
    assert agent_from_str.id.value == raw_uuid

    agent_from_uuid = Agent.create("B", "b@test.com", "Team", agent_id=raw_uuid)
    assert agent_from_uuid.id.value == raw_uuid

    agent_from_vo = Agent.create("C", "c@test.com", "Team", agent_id=vo_agent_id)
    assert agent_from_vo.id == vo_agent_id


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

def test_routing_rule_entity_creation():
    agent_id = uuid.uuid4()
    rule = RoutingRule.create(
        min_score=30,
        target_team="Sales",
        assignment_strategy="LOWEST_LOAD",
        target_agent_ids=[str(agent_id)],
        rule_id=str(uuid.uuid4()),
    )
    assert rule.min_score == 30
    assert rule.assignment_strategy == AssignmentStrategy.LOWEST_LOAD
    assert rule.target_agent_ids == [agent_id]
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


