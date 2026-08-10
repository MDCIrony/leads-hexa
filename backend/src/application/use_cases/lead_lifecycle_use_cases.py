from typing import Optional
from uuid import UUID

from application.dtos.commands import AssignLeadCommand, DiscardLeadCommand, LeadsPageResult
from application.dtos.queries import GetLeadQuery, GetMyLeadsQuery
from application.ports.input.lead_lifecycle_use_case_ports import (
    AssignLeadInputPort,
    DiscardLeadInputPort,
    GetLeadInputPort,
    GetMyLeadsInputPort,
)
from application.ports.output.domain_event_publisher_port import DomainEventPublisherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent
from domain.entities.lead import Lead
from domain.events.notification_events import LeadAssigned, LeadReassigned
from domain.exceptions import DomainException
from domain.value_objects.enums import LeadStatus


def _get_owned_lead(uow: UnitOfWorkPort, tenant_id: UUID, lead_id: UUID) -> Lead:
    """Scoped through get_by_id_and_tenant so a lead from another
    organization reads back as missing rather than confirming it exists."""
    lead = uow.leads.get_by_id_and_tenant(lead_id, tenant_id)
    if lead is None:
        raise DomainException("El lead no existe", error_code="LEAD_NOT_FOUND")
    return lead


def _get_owned_agent(uow: UnitOfWorkPort, tenant_id: UUID, agent_id: UUID) -> Agent:
    """Same existence-hiding reason as _get_owned_lead: an agent belonging to
    another organization must read back as missing, not merely forbidden."""
    agent = uow.agents.get_by_id_and_tenant(agent_id, tenant_id)
    if agent is None:
        raise DomainException("El asesor no existe", error_code="AGENT_NOT_FOUND")
    return agent


class AssignLeadUseCase(AssignLeadInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        event_publisher: Optional[DomainEventPublisherPort] = None,
    ) -> None:
        self.uow = uow
        self.event_publisher = event_publisher

    def execute(self, command: AssignLeadCommand) -> Lead:
        previous_agent_id = None
        with self.uow:
            lead = _get_owned_lead(self.uow, command.tenant_id, command.lead_id)
            agent = _get_owned_agent(self.uow, command.tenant_id, command.agent_id)
            # One action for the manager regardless of the lead's current
            # state: reassign_to is explicit about replacing an existing
            # agent, assign_to refuses to do that silently.
            reassigning = lead.status == LeadStatus.ASSIGNED
            if reassigning:
                previous_agent_id = lead.assigned_agent_id
                lead.reassign_to(agent.id, agent.tenant_id)
            else:
                lead.assign_to(agent.id, agent.tenant_id)
            saved_lead = self.uow.leads.save(lead)

        # Published after the transaction commits (N1): a failing notice must
        # not undo an assignment that already happened.
        if self.event_publisher:
            if reassigning:
                self.event_publisher.publish(LeadReassigned(
                    tenant_id=str(saved_lead.tenant_id.value),
                    lead_id=str(saved_lead.id),
                    agent_id=str(agent.id),
                    previous_agent_id=str(previous_agent_id) if previous_agent_id else None,
                ))
            else:
                self.event_publisher.publish(LeadAssigned(
                    tenant_id=str(saved_lead.tenant_id.value),
                    lead_id=str(saved_lead.id),
                    agent_id=str(agent.id),
                ))

        return saved_lead


class DiscardLeadUseCase(DiscardLeadInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: DiscardLeadCommand) -> Lead:
        with self.uow:
            lead = _get_owned_lead(self.uow, command.tenant_id, command.lead_id)
            lead.discard(command.reason)
            return self.uow.leads.save(lead)


class GetMyLeadsUseCase(GetMyLeadsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetMyLeadsQuery) -> LeadsPageResult:
        status = None
        if query.status is not None:
            try:
                status = LeadStatus(query.status)
            except ValueError:
                raise DomainException(
                    f"Unknown lead status: {query.status}",
                    error_code="INVALID_LEAD_STATUS",
                )
        with self.uow:
            items = self.uow.leads.list_by_agent(
                query.tenant_id, query.agent_id,
                status=status, search=query.search,
                limit=query.limit, offset=query.offset,
            )
            total = self.uow.leads.count_by_agent(
                query.tenant_id, query.agent_id, status=status, search=query.search,
            )
        return LeadsPageResult(items=items, total=total)


class GetLeadUseCase(GetLeadInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetLeadQuery) -> Lead:
        with self.uow:
            return _get_owned_lead(self.uow, query.tenant_id, query.lead_id)
