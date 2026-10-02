import uuid

import pytest

from application.dtos.commands import AssignLeadCommand, DiscardLeadCommand
from application.dtos.queries import GetMyLeadsQuery
from application.use_cases.lead_lifecycle_use_cases import (
    AssignLeadUseCase,
    DiscardLeadUseCase,
    GetMyLeadsUseCase,
)
from domain.leads.lead import Lead
from domain.exceptions import DomainException
from domain.value_objects.enums import AgentRole, LeadStatus
from tests.unit.mocks.in_memory_advisor_repo import ProjectionOnlyDirectory, make_advisor
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT = uuid.uuid4()
_OTHER = uuid.uuid4()


def _lead(tenant_id: uuid.UUID = _TENANT, status: LeadStatus = LeadStatus.UNASSIGNED) -> Lead:
    return Lead.create(
        tenant_id=tenant_id, source_id=uuid.uuid4(), first_name="Ana", last_name="Diaz", email="ana@x.test",
        company="Acme", budget=1000, industry="tech", status=status,
    )


def _agent(tenant_id: uuid.UUID = _TENANT):
    return make_advisor(
        "Sales One", role=AgentRole.AGENT, tenant_id=tenant_id
    )


def test_assigning_moves_the_lead_to_the_agent():
    uow = InMemoryUnitOfWork()
    lead, agent = _lead(), _agent()
    uow.leads.save(lead)
    uow.advisors.seed(agent)

    result = AssignLeadUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
        AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=agent.id.value)
    )

    assert result.status == LeadStatus.ASSIGNED.value
    stored = uow.leads.get_by_id(lead.id.value)
    assert stored.assigned_agent_id.value == agent.id.value
    assert stored.assigned_at is not None


def test_assigning_a_lead_of_another_organization_is_not_found():
    """Not Forbidden: a 403 would confirm the lead exists elsewhere."""
    uow = InMemoryUnitOfWork()
    lead, agent = _lead(tenant_id=_OTHER), _agent()
    uow.leads.save(lead)
    uow.advisors.seed(agent)

    with pytest.raises(DomainException) as exc:
        AssignLeadUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
            AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=agent.id.value)
        )
    assert exc.value.error_code == "LEAD_NOT_FOUND"


def test_assigning_an_agent_of_another_organization_is_refused():
    """Not CROSS_TENANT_ASSIGNMENT: the agent is looked up scoped to the
    caller's own tenant (get_by_id_and_tenant), the same existence-hiding
    rule as the lead lookup above, so a foreign agent resolves to "missing"
    before Lead._bind_agent's own cross-tenant guard ever runs."""
    uow = InMemoryUnitOfWork()
    lead, agent = _lead(), _agent(tenant_id=_OTHER)
    uow.leads.save(lead)
    uow.advisors.seed(agent)

    with pytest.raises(DomainException) as exc:
        AssignLeadUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
            AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=agent.id.value)
        )
    assert exc.value.error_code == "AGENT_NOT_FOUND"


def test_reassigning_an_already_assigned_lead_lands_on_the_new_agent():
    uow = InMemoryUnitOfWork()
    lead = _lead()
    first_agent, second_agent = _agent(), _agent()
    lead.assign_to(first_agent.id, first_agent.tenant_id)
    uow.leads.save(lead)
    uow.advisors.seed(first_agent)
    uow.advisors.seed(second_agent)

    result = AssignLeadUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
        AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=second_agent.id.value)
    )

    assert result.status == LeadStatus.ASSIGNED.value
    assert result.assigned_agent_id.value == second_agent.id.value
    stored = uow.leads.get_by_id(lead.id.value)
    assert stored.assigned_agent_id.value == second_agent.id.value


def test_assigning_by_hand_republishes_the_lead_to_the_customer():
    """Admission published it as UNASSIGNED because routing found nobody. The
    customer's copy stays frozen there unless the manual assignment records
    the contract again, this time with an owner — through the outbox
    (ADR-0025)."""
    uow = InMemoryUnitOfWork()
    lead, agent = _lead(), _agent()
    uow.leads.save(lead)
    uow.advisors.seed(agent)

    AssignLeadUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
        AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=agent.id.value)
    )

    internal = uow.outbox.list_unpublished("internal", 10)
    assert [entry.event_type for entry in internal] == ["LeadAssigned"]
    assert internal[0].payload["agent_id"] == str(agent.id)

    outbox_entries = uow.outbox.list_unpublished("product", 10)
    assert [entry.event_type for entry in outbox_entries] == ["LeadProcessedEvent"]
    outbound = outbox_entries[0].payload
    assert outbound["status"] == LeadStatus.ASSIGNED.value
    assert outbound["assigned_agent_id"] == str(agent.id)
    assert outbound["assigned_at"] is not None
    assert outbound["lead_id"] == str(lead.id)



def test_reassigning_records_lead_reassigned_with_the_previous_agent():
    uow = InMemoryUnitOfWork()
    first_agent, second_agent = _agent(), _agent()
    lead = _lead()
    lead.assign_to(first_agent.id, first_agent.tenant_id)
    uow.leads.save(lead)
    uow.advisors.seed(first_agent)
    uow.advisors.seed(second_agent)

    AssignLeadUseCase(uow, ProjectionOnlyDirectory(uow)).execute(
        AssignLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, agent_id=second_agent.id.value)
    )

    internal = uow.outbox.list_unpublished("internal", 10)
    assert [entry.event_type for entry in internal] == ["LeadReassigned"]
    assert internal[0].partition_key == str(lead.id)
    assert internal[0].payload["agent_id"] == str(second_agent.id)
    assert internal[0].payload["previous_agent_id"] == str(first_agent.id)

def test_discarding_records_the_reason():
    uow = InMemoryUnitOfWork()
    lead = _lead()
    uow.leads.save(lead)

    result = DiscardLeadUseCase(uow).execute(
        DiscardLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, reason="Presupuesto insuficiente")
    )

    assert result.status == LeadStatus.DISCARDED.value
    assert result.discard_reason == "Presupuesto insuficiente"
    stored = uow.leads.get_by_id(lead.id.value)
    assert stored.status == LeadStatus.DISCARDED
    assert stored.discard_reason == "Presupuesto insuficiente"


def test_discarding_without_a_reason_is_refused():
    uow = InMemoryUnitOfWork()
    lead = _lead()
    uow.leads.save(lead)

    with pytest.raises(DomainException) as exc:
        DiscardLeadUseCase(uow).execute(
            DiscardLeadCommand(tenant_id=_TENANT, lead_id=lead.id.value, reason="")
        )
    assert exc.value.error_code == "DISCARD_WITHOUT_REASON"


def test_my_leads_only_returns_the_requesting_agent_leads():
    uow = InMemoryUnitOfWork()
    agent_one, agent_two = _agent(), _agent()
    lead_one, lead_two = _lead(), _lead()
    lead_one.assign_to(agent_one.id, agent_one.tenant_id)
    lead_two.assign_to(agent_two.id, agent_two.tenant_id)
    uow.leads.save(lead_one)
    uow.leads.save(lead_two)
    uow.advisors.seed(agent_one)
    uow.advisors.seed(agent_two)

    result = GetMyLeadsUseCase(uow).execute(
        GetMyLeadsQuery(tenant_id=_TENANT, agent_id=agent_one.id.value)
    )

    assert [lead.id.value for lead in result.items] == [lead_one.id.value]
    assert result.total == 1
