import uuid
from unittest.mock import Mock
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase, payload_of
from application.dtos.commands import IngestLeadCommand
from domain.entities.intake_record import IntakeRecord
from domain.events.lead_events import LeadProcessedEvent
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def test_ingest_lead_publishes_event() -> None:
    uow = InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        InMemoryAgentRepository(),
        groups=InMemorySalesGroupRepository(),
    )
    mock_event_publisher = Mock()

    use_case = IngestLeadUseCase(
        uow=uow,
        event_publisher=mock_event_publisher,
    )

    tenant_id_val = uuid.uuid4()

    command = IngestLeadCommand(
        tenant_id=tenant_id_val,
        source_id=uuid.uuid4(),
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone=None,
        company="Acme Corp",
        budget=5000.0,
        industry="Tech",
        custom_attributes={},
    )
    existing = uow.intake_records.save(
        IntakeRecord.create(tenant_id=command.tenant_id, source_id=command.source_id, payload=payload_of(command))
    )

    result = use_case.execute(command, existing_record=existing)

    assert result.error is None
    assert mock_event_publisher.publish.call_count == 1
    event_arg = mock_event_publisher.publish.call_args[0][0]
    assert isinstance(event_arg, LeadProcessedEvent)
    assert event_arg.tenant_id == str(tenant_id_val)
