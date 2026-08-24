import uuid
from unittest.mock import Mock
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase, payload_of
from application.dtos.commands import IngestLeadCommand
from domain.entities.disqualification_rule import DisqualificationRule
from domain.entities.intake_record import IntakeRecord
from domain.events.notification_events import LeadLeftUnassigned
from domain.value_objects.criterion import Criterion
from domain.value_objects.enums import Operator
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
    # LeadLeftUnassigned only (F3a): no rules and no available agent leaves
    # the lead UNASSIGNED rather than routed. LeadProcessedEvent went through
    # the outbox instead of the in-process publisher (ADR-0025).
    assert mock_event_publisher.publish.call_count == 1
    published = [call.args[0] for call in mock_event_publisher.publish.call_args_list]
    assert isinstance(published[0], LeadLeftUnassigned)
    assert published[0].tenant_id == str(tenant_id_val)

    outbox_entries = uow.outbox.list_unpublished(10)
    assert len(outbox_entries) == 1
    assert outbox_entries[0].event_type == "LeadProcessedEvent"
    assert outbox_entries[0].tenant_id == str(tenant_id_val)
    # The whole lead travels, so the receiver never has to ask us who it is.
    assert outbox_entries[0].payload["first_name"] == "Jane"
    assert outbox_entries[0].payload["company"] == "Acme Corp"
    assert outbox_entries[0].payload["industry"] == "Tech"
    assert outbox_entries[0].payload["source_id"] == str(command.source_id)
    assert outbox_entries[0].payload["budget"] == "5000.00"


def test_a_disqualified_lead_does_not_travel_as_processed() -> None:
    """The outbound channel sells what our rules kept. A lead a rule ruled out
    is an audit trail, and publishing it as processed handed the customer the
    filtering we are paid to do."""
    uow = InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        InMemoryAgentRepository(),
        groups=InMemorySalesGroupRepository(),
    )
    mock_event_publisher = Mock()
    tenant_id_val = uuid.uuid4()
    uow.disqualification_rules.save(DisqualificationRule.create(
        tenant_id=tenant_id_val,
        name="Sin forma de contactar",
        conditions=[Criterion.create(field="phone", operator=Operator.IS_EMPTY)],
    ))

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

    use_case = IngestLeadUseCase(uow=uow, event_publisher=mock_event_publisher)
    result = use_case.execute(command, existing_record=existing)

    assert result.status == "DISQUALIFIED"
    # Nothing travels through the in-process publisher: a disqualified lead
    # sets neither assigned_agent nor left_unassigned, so _publish_notices
    # has no internal event to send. LeadDisqualified went through the
    # outbox instead (ADR-0025).
    assert mock_event_publisher.publish.call_count == 0

    outbox_entries = uow.outbox.list_unpublished(10)
    assert [entry.event_type for entry in outbox_entries] == ["LeadDisqualified"]
    assert outbox_entries[0].payload["reason"] == "Sin forma de contactar"
    assert outbox_entries[0].payload["lead_id"] == result.lead_id
