import uuid
from domain.entities import Lead, Agent, ScoringRule, RoutingRule, WebhookConfig
from domain.value_objects import (
    LeadId,
    TenantId,
    AgentId,
    EmailAddress,
    Money,
    LeadStatus,
    Operator,
    AssignmentStrategy,
    WebhookEventType,
)

def test_lead_entity_lifecycle():
    lead = Lead(
        id=LeadId(),
        tenant_id=TenantId(),
        first_name="Maria",
        last_name="Gomez",
        email=EmailAddress("mgomez@techcorp.com"),
        company="TechCorp Inc",
        budget=Money(15000),
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

def test_agent_entity():
    agent = Agent(
        id=AgentId(),
        name="Carlos Lopez",
        email="clopez@sales.com",
        team="Enterprise Sales",
        active_leads_count=2,
    )
    assert agent.is_active is True
    assert agent.active_leads_count == 2

def test_scoring_rule_entity():
    rule = ScoringRule(
        id=uuid.uuid4(),
        name="High Budget",
        field="budget",
        operator=Operator.GREATER_THAN,
        value=10000,
        score_delta=25,
    )
    assert rule.score_delta == 25
