import json
import uuid
from uuid import uuid4

from application.dtos.commands import IngestLeadCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase, payload_of
from domain.entities import Agent, AssignmentRule, ScoringRule, SalesGroup
from domain.entities.intake_record import IntakeRecord
from domain.value_objects import Operator, AssignmentStrategy
from domain.value_objects.criterion import Criterion
from domain.value_objects.enums import IntakeRecordStatus
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork
import pytest
from unittest.mock import MagicMock

def test_ingest_lead_use_case_successful_flow():
    tenant_id = uuid.uuid4()
    lead_repo = InMemoryLeadRepository()
    rule_repo = InMemoryRuleRepository()
    agent_repo = InMemoryAgentRepository()
    group_repo = InMemorySalesGroupRepository()

    # Pre-cargar regla de scoring (+35 pts)
    rule_repo.save_scoring_rule(
        tenant_id,
        ScoringRule.create(
            tenant_id=tenant_id,
            name="Tech Corp High Budget",
            conditions=[Criterion.create(field="budget", operator=Operator.GREATER_THAN, value=10000)],
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

    uow = InMemoryUnitOfWork(lead_repo, rule_repo, agent_repo, groups=group_repo)
    use_case = IngestLeadUseCase(uow=uow)

    cmd = IngestLeadCommand(
        tenant_id=tenant_id,
        source_id=uuid.uuid4(),
        first_name="Maria",
        last_name="Gomez",
        email="mgomez@techcorp.com",
        company="TechCorp Inc",
        budget=15000.0,
        industry="Technology",
        custom_attributes={"employee_count": 150},
    )
    existing = uow.intake_records.save(
        IntakeRecord.create(tenant_id=cmd.tenant_id, source_id=cmd.source_id, payload=payload_of(cmd))
    )

    result = use_case.execute(cmd, existing_record=existing)

    assert result.status == "ASSIGNED"
    assert result.score == 35
    assert result.assigned_agent_id == str(agent.id)
    # The outbound fact this flow must leave behind (ADR-0025): recorded in
    # the outbox inside the same transaction, not dispatched to a webhook
    # directly — WebhookOutboundDispatcher and OutboxRelay own delivery now.
    outbox_entries = uow.outbox.list_unpublished("product", 10)
    assert [entry.event_type for entry in outbox_entries] == ["LeadProcessedEvent"]
    assert outbox_entries[0].payload["assigned_agent_id"] == str(agent.id)

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
        source_id=uuid.uuid4(),
        first_name="Bad",
        last_name="User",
        email="invalid-email-format",
        company="Corp",
        budget=5000.0,
        industry="Tech",
    )
    existing = uow.intake_records.save(
        IntakeRecord.create(tenant_id=cmd.tenant_id, source_id=cmd.source_id, payload=payload_of(cmd))
    )

    result = use_case.execute(cmd, existing_record=existing)

    # T4: a rejected payload is not lost. It lands as a REJECTED
    # IntakeRecord instead of the retired LeadStatus.FAILED.
    assert result.status == "REJECTED"
    assert result.intake_record_id != ""
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
        source_id=uuid.uuid4(),
        first_name="Test",
        last_name="User",
        email="test@user.com",
        company="Test Co",
        budget=1000.0,
        industry="Tech",
        custom_attributes={},
        phone="123456789",
    )
    existing = IntakeRecord.create(
        tenant_id=command.tenant_id, source_id=command.source_id, payload=payload_of(command)
    )

    # Act & Assert
    with pytest.raises(Exception, match="Database failure"):
        use_case.execute(command, existing_record=existing)

    # El UnitOfWorkPort debió hacer rollback
    mock_uow.rollback.assert_called_once()
    mock_uow.commit.assert_not_called()

def test_payload_of_normalises_a_non_finite_budget_to_null():
    """A blank budget cell reaches here as NaN, and json.dumps emits a bare
    NaN token that PostgreSQL rejects as invalid JSONB — which fails the whole
    batch insert instead of just this row."""
    command = IngestLeadCommand(
        tenant_id=uuid4(),
        source_id=uuid4(),
        first_name="Juan",
        last_name="Perez",
        company="SmallBiz Local",
        budget=float("nan"),
        industry="Retail",
    )

    payload = payload_of(command)

    assert payload["budget"] is None
    # allow_nan=False is what makes this assertion real: by default json.dumps
    # emits the bare NaN token happily, and that token is what Postgres rejects.
    json.dumps(payload, allow_nan=False)

def test_ingest_lead_use_case_rejects_a_non_finite_budget():
    """Without the guard in ``Money``, a NaN budget escaped as
    ``decimal.InvalidOperation`` and no caller could translate it into a
    clean rejection. This exercises that translation directly -- calling the
    use case with a raw NaN command, bypassing both ``payload_of`` and
    PostgreSQL entirely."""
    tenant_id = uuid.uuid4()
    uow = InMemoryUnitOfWork(
        InMemoryLeadRepository(), InMemoryRuleRepository(), InMemoryAgentRepository()
    )
    use_case = IngestLeadUseCase(
        uow=uow,
    )

    cmd = IngestLeadCommand(
        tenant_id=tenant_id,
        source_id=uuid.uuid4(),
        first_name="Bad",
        last_name="Budget",
        email="test@example.com",
        company="Corp",
        budget=float("nan"),
        industry="Tech",
    )
    existing = uow.intake_records.save(
        IntakeRecord.create(tenant_id=cmd.tenant_id, source_id=cmd.source_id, payload=payload_of(cmd))
    )

    result = use_case.execute(cmd, existing_record=existing)

    assert result.status == IntakeRecordStatus.REJECTED.value
    assert result.error_code == "INVALID_BUDGET"
