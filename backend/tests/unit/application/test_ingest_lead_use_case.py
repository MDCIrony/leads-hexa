import uuid
from application.dtos.commands import IngestLeadCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from domain.entities import Agent, AssignmentRule, ScoringRule, SalesGroup
from domain.value_objects import Operator, AssignmentStrategy
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_webhook_dispatcher import InMemoryWebhookDispatcher
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork
import pytest
from unittest.mock import MagicMock

def test_ingest_lead_use_case_successful_flow():
    tenant_id = uuid.uuid4()
    lead_repo = InMemoryLeadRepository()
    rule_repo = InMemoryRuleRepository()
    agent_repo = InMemoryAgentRepository()
    group_repo = InMemorySalesGroupRepository()
    webhook_dispatcher = InMemoryWebhookDispatcher()

    # Pre-cargar regla de scoring (+35 pts)
    rule_repo.save_scoring_rule(
        tenant_id,
        ScoringRule.create(
            name="Tech Corp High Budget",
            field="budget",
            operator=Operator.GREATER_THAN,
            value=10000,
            score_delta=35,
        ),
    )

    # Pre-cargar grupo y agente disponible
    group = group_repo.save(SalesGroup.create(tenant_id=tenant_id, name="Sales"))
    agent = Agent.create(
        name="Carlos Lopez",
        email="clopez@sales.com",
        group_id=group.id.value,
        tenant_id=tenant_id,
    )
    agent_repo.save(agent)

    # Pre-cargar regla de asignación
    rule_repo.save_assignment_rule(
        tenant_id,
        AssignmentRule.create(
            tenant_id=tenant_id,
            name="Sales band",
            min_score=30,
            target_group_id=group.id.value,
            strategy=AssignmentStrategy.LOWEST_LOAD,
        ),
    )

    from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher
    from application.handlers.webhook_event_handler import WebhookEventHandler
    from domain.events.lead_events import LeadProcessedEvent
    from domain.entities.webhook import WebhookConfig
    from domain.value_objects.enums import WebhookEventType

    event_publisher = InMemoryEventPublisher()
    mock_webhook_repo = MagicMock()
    mock_webhook_repo.get_by_tenant_and_event.return_value = [
        WebhookConfig.create(
            tenant_id=str(tenant_id),
            event_type=WebhookEventType.LEAD_PROCESSED,
            target_url="https://hooks.example.com/lead",
            secret_token="secret",
        )
    ]
    webhook_handler = WebhookEventHandler(
        webhook_repo=mock_webhook_repo,
        webhook_dispatcher=webhook_dispatcher,
    )
    event_publisher.subscribe(LeadProcessedEvent, webhook_handler.handle_lead_processed)

    uow = InMemoryUnitOfWork(lead_repo, rule_repo, agent_repo, groups=group_repo)
    use_case = IngestLeadUseCase(
        uow=uow,
        event_publisher=event_publisher,
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
    uow = InMemoryUnitOfWork(
        InMemoryLeadRepository(), InMemoryRuleRepository(), InMemoryAgentRepository()
    )
    use_case = IngestLeadUseCase(
        uow=uow,
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
    assert result.error_code == "INVALID_EMAIL"

def test_rollback_on_persistence_error():
    # Arrange
    mock_uow = MagicMock()
    mock_uow.__enter__.return_value = mock_uow
    def mock_exit(exc_type, exc_val, exc_tb):
        if exc_type is not None:
            mock_uow.rollback()
        else:
            mock_uow.commit()
        return False
    mock_uow.__exit__.side_effect = mock_exit
    mock_uow.rules.get_scoring_rules_by_tenant.return_value = []
    mock_uow.rules.get_assignment_rules_by_tenant.return_value = []
    mock_uow.agents.get_available_agents.return_value = []
    mock_uow.groups.list_by_tenant.return_value = []
    mock_uow.leads.active_load_by_agent.return_value = {}

    # Simular que al intentar guardar el Lead se lanza un error
    mock_uow.leads.save.side_effect = Exception("Database failure")

    use_case = IngestLeadUseCase(uow=mock_uow)

    command = IngestLeadCommand(
        tenant_id=uuid.uuid4(),
        first_name="Test",
        last_name="User",
        email="test@user.com",
        company="Test Co",
        budget=1000.0,
        industry="Tech",
        custom_attributes={},
        phone="123456789",
    )

    # Act & Assert
    with pytest.raises(Exception, match="Database failure"):
        use_case.execute(command)

    # El UnitOfWorkPort debió hacer rollback
    mock_uow.rollback.assert_called_once()
    mock_uow.commit.assert_not_called()
