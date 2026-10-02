import uuid

import pytest

from application.use_cases.intake.payloads import payload_of
from application.dtos.commands import IngestLeadCommand
from domain.entities import AssignmentRule
from domain.entities.disqualification_rule import DisqualificationRule
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.criterion import Criterion
from domain.value_objects.enums import Operator
from tests.unit.mocks.in_memory_advisor_repo import make_advisor
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork
from tests.unit.mocks.in_process_ingest import in_process_ingest


def _uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        groups=InMemorySalesGroupRepository(),
    )


def _command(tenant_id: uuid.UUID, **overrides) -> IngestLeadCommand:
    fields = dict(
        tenant_id=tenant_id,
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
    fields.update(overrides)
    return IngestLeadCommand(**fields)


def _ingest(uow: InMemoryUnitOfWork, command: IngestLeadCommand):
    existing = uow.intake_records.save(
        IntakeRecord.create(tenant_id=command.tenant_id, source_id=command.source_id, payload=payload_of(command))
    )
    return in_process_ingest(uow).execute(command, existing_record=existing), existing


def _internal(uow: InMemoryUnitOfWork):
    return uow.outbox.list_unpublished("internal", 10)


def test_an_assigned_lead_records_one_lead_assigned_next_to_the_product_event() -> None:
    uow = _uow()
    tenant_id = uuid.uuid4()
    agent = uow.advisors.seed(make_advisor(name="Carlos", tenant_id=tenant_id))
    uow.rules.save_assignment_rule(
        tenant_id,
        AssignmentRule.create(tenant_id=tenant_id, name="Catch-all", target_agent_ids=[agent.id.value]),
    )

    result, _ = _ingest(uow, _command(tenant_id))

    assert result.assigned_agent_id == str(agent.id)
    internal = _internal(uow)
    assert [entry.event_type for entry in internal] == ["LeadAssigned"]
    assert internal[0].tenant_id == str(tenant_id)
    assert internal[0].partition_key == result.lead_id
    assert internal[0].payload["agent_id"] == str(agent.id)
    assert [entry.event_type for entry in uow.outbox.list_unpublished("product", 10)] == ["LeadProcessedEvent"]


def test_a_lead_nobody_can_take_records_lead_left_unassigned() -> None:
    uow = _uow()
    tenant_id = uuid.uuid4()

    result, _ = _ingest(uow, _command(tenant_id))

    assert result.status == "UNASSIGNED"
    internal = _internal(uow)
    assert [entry.event_type for entry in internal] == ["LeadLeftUnassigned"]
    assert internal[0].payload["lead_id"] == result.lead_id

    outbox_entries = uow.outbox.list_unpublished("product", 10)
    assert len(outbox_entries) == 1
    assert outbox_entries[0].event_type == "LeadProcessedEvent"
    assert outbox_entries[0].tenant_id == str(tenant_id)
    # The whole lead travels, so the receiver never has to ask us who it is.
    assert outbox_entries[0].payload["first_name"] == "Jane"
    assert outbox_entries[0].payload["company"] == "Acme Corp"
    assert outbox_entries[0].payload["industry"] == "Tech"
    assert outbox_entries[0].payload["budget"] == "5000.00"


def test_an_invalid_payload_records_intake_rejected() -> None:
    uow = _uow()
    tenant_id = uuid.uuid4()

    result, existing = _ingest(uow, _command(tenant_id, email="not-an-email"))

    assert result.status == "REJECTED"
    internal = _internal(uow)
    assert [entry.event_type for entry in internal] == ["IntakeRejected"]
    assert internal[0].partition_key == str(existing.id)
    assert internal[0].payload["reason"] == result.error
    assert uow.outbox.list_unpublished("product", 10) == []


def test_a_rolled_back_ingestion_records_nothing() -> None:
    """The commit is the last thing that can fail; whatever was recorded
    before it must go with the transaction, not survive it."""

    class _CommitFails(InMemoryUnitOfWork):
        def commit(self) -> None:
            # What a refused commit leaves behind in Postgres: nothing.
            self.rollback()
            raise RuntimeError("commit refused")

    uow = _CommitFails(InMemoryLeadRepository(), InMemoryRuleRepository())

    with pytest.raises(RuntimeError):
        _ingest(uow, _command(uuid.uuid4()))

    assert _internal(uow) == []
    assert uow.outbox.list_unpublished("product", 10) == []


def test_a_disqualified_lead_does_not_travel_as_processed() -> None:
    """The outbound channel sells what our rules kept. A lead a rule ruled out
    is an audit trail, and publishing it as processed handed the customer the
    filtering we are paid to do."""
    uow = _uow()
    tenant_id = uuid.uuid4()
    uow.disqualification_rules.save(DisqualificationRule.create(
        tenant_id=tenant_id,
        name="Sin forma de contactar",
        conditions=[Criterion.create(field="phone", operator=Operator.IS_EMPTY)],
    ))

    result, _ = _ingest(uow, _command(tenant_id))

    assert result.status == "DISQUALIFIED"
    # Nobody has to act on a lead a rule ruled out: no internal notice.
    assert _internal(uow) == []

    outbox_entries = uow.outbox.list_unpublished("product", 10)
    assert [entry.event_type for entry in outbox_entries] == ["LeadDisqualified"]
    assert outbox_entries[0].payload["reason"] == "Sin forma de contactar"
    assert outbox_entries[0].payload["lead_id"] == result.lead_id
