import uuid
from unittest.mock import Mock
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase, payload_of
from application.dtos.commands import IngestLeadCommand
from domain.entities.intake_record import IntakeRecord
from domain.events.lead_events import LeadProcessedEvent
from domain.events.notification_events import LeadLeftUnassigned
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
    # LeadProcessedEvent always, plus LeadLeftUnassigned (F3a): no rules and
    # no available agent leaves the lead UNASSIGNED rather than routed.
    assert mock_event_publisher.publish.call_count == 2
    published = [call.args[0] for call in mock_event_publisher.publish.call_args_list]
    assert isinstance(published[0], LeadProcessedEvent)
    assert published[0].tenant_id == str(tenant_id_val)
    assert isinstance(published[1], LeadLeftUnassigned)
    assert published[1].tenant_id == str(tenant_id_val)
