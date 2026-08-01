import uuid
from domain.entities import Lead, Agent, RoutingRule
from domain.value_objects import AssignmentStrategy, LeadStatus
from domain.services import RouterEngine

def test_router_engine_lowest_load_strategy():
    lead = Lead.create(
        tenant_id=uuid.uuid4(),
        first_name="Maria",
        last_name="Gomez",
        email="mgomez@techcorp.com",
        company="TechCorp Inc",
        budget=15000,
        industry="Technology",
    )
    lead.apply_score(50)

    agent1 = Agent.create(name="Carlos", email="c@sales.com", team="Enterprise", active_leads_count=5)
    agent2 = Agent.create(name="Ana", email="a@sales.com", team="Enterprise", active_leads_count=2)

    routing_rules = [
        RoutingRule.create(
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
