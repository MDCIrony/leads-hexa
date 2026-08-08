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


def _qualified_lead() -> Lead:
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
    return lead


def test_round_robin_strategy_advances_across_repeated_calls_on_the_same_engine():
    """The round-robin index lives on the engine instance, not on a single
    call — this is exactly the state a composition root must keep alive by
    sharing one engine, or every routing decision lands on the same agent."""
    agent1 = Agent.create(name="Carlos", email="c@sales.com", team="Sales", active_leads_count=0)
    agent2 = Agent.create(name="Ana", email="a@sales.com", team="Sales", active_leads_count=0)

    routing_rules = [
        RoutingRule.create(
            min_score=30,
            target_team="Sales",
            assignment_strategy=AssignmentStrategy.ROUND_ROBIN,
        )
    ]

    router = RouterEngine()
    first_pick = router.select_agent(_qualified_lead(), routing_rules, [agent1, agent2])
    second_pick = router.select_agent(_qualified_lead(), routing_rules, [agent1, agent2])

    assert first_pick.id != second_pick.id
    assert {first_pick.id, second_pick.id} == {agent1.id, agent2.id}
