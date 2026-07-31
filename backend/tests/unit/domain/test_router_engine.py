import uuid
from domain.entities import Lead, Agent, RoutingRule
from domain.value_objects import (
    LeadId,
    TenantId,
    AgentId,
    EmailAddress,
    Money,
    AssignmentStrategy,
    LeadStatus,
)
from domain.services import RouterEngine

def test_router_engine_lowest_load_strategy():
    lead = Lead(
        id=LeadId(),
        tenant_id=TenantId(),
        first_name="Maria",
        last_name="Gomez",
        email=EmailAddress("mgomez@techcorp.com"),
        company="TechCorp Inc",
        budget=Money(15000),
        industry="Technology",
    )
    lead.apply_score(50)

    agent1 = Agent(id=AgentId(), name="Carlos", email="c@sales.com", team="Enterprise", active_leads_count=5)
    agent2 = Agent(id=AgentId(), name="Ana", email="a@sales.com", team="Enterprise", active_leads_count=2)

    routing_rules = [
        RoutingRule(
            id=uuid.uuid4(),
            min_score=30,
            target_team="Enterprise",
            assignment_strategy=AssignmentStrategy.LOWEST_LOAD,
        )
    ]

    router = RouterEngine()
    selected_agent = router.select_agent(lead, routing_rules, [agent1, agent2])

    assert selected_agent is not None
    assert selected_agent.id == agent2.id
    assert lead.status == LeadStatus.ASSIGNED
    assert lead.assigned_agent_id == agent2.id
