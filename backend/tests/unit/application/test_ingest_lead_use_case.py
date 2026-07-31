import uuid
from application.dtos.commands import IngestLeadCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from domain.entities import ScoringRule, RoutingRule, Agent
from domain.value_objects import Operator, AssignmentStrategy, AgentId
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_webhook_dispatcher import InMemoryWebhookDispatcher

def test_ingest_lead_use_case_successful_flow():
    tenant_id = uuid.uuid4()
    lead_repo = InMemoryLeadRepository()
    rule_repo = InMemoryRuleRepository()
    agent_repo = InMemoryAgentRepository()
    webhook_dispatcher = InMemoryWebhookDispatcher()

    # Pre-cargar regla de scoring (+35 pts)
    rule_repo.save_scoring_rule(
        tenant_id,
        ScoringRule(
            id=uuid.uuid4(),
            name="Tech Corp High Budget",
            field="budget",
            operator=Operator.GREATER_THAN,
            value=10000,
            score_delta=35,
        ),
    )

    # Pre-cargar regla de routing
    rule_repo.save_routing_rule(
        tenant_id,
        RoutingRule(
            id=uuid.uuid4(),
            min_score=30,
            target_team="Sales",
            assignment_strategy=AssignmentStrategy.LOWEST_LOAD,
        ),
    )

    # Pre-cargar agente disponible
    agent = Agent(
        id=AgentId(),
        name="Carlos Lopez",
        email="clopez@sales.com",
        team="Sales",
        active_leads_count=0,
    )
    agent_repo.save(agent)

    use_case = IngestLeadUseCase(
        lead_repo=lead_repo,
        rule_repo=rule_repo,
        agent_repo=agent_repo,
        webhook_dispatcher=webhook_dispatcher,
    )

    cmd = IngestLeadCommand(
        tenant_id=tenant_id,
        first_name="Maria",
        last_name="Gomez",
        email="mgomez@techcorp.com",
        company="TechCorp Inc",
        budget=15000.0,
        industry="Technology",
        custom_attributes={"employee_count": 150},
    )

    result = use_case.execute(cmd)

    assert result.status == "ASSIGNED"
    assert result.score == 35
    assert result.assigned_agent_id == str(agent.id)
    assert result.webhook_dispatched is True
    assert len(webhook_dispatcher.dispatched_events) == 1

def test_ingest_lead_use_case_invalid_email_error():
    tenant_id = uuid.uuid4()
    use_case = IngestLeadUseCase(
        lead_repo=InMemoryLeadRepository(),
        rule_repo=InMemoryRuleRepository(),
        agent_repo=InMemoryAgentRepository(),
    )

    cmd = IngestLeadCommand(
        tenant_id=tenant_id,
        first_name="Bad",
        last_name="User",
        email="invalid-email-format",
        company="Corp",
        budget=5000.0,
        industry="Tech",
    )

    result = use_case.execute(cmd)

    assert result.status == "FAILED"
    assert result.error is not None
    assert "correo electrónico inválido" in result.error
