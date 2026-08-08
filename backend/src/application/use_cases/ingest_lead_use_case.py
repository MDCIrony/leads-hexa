from typing import Dict, Optional
from uuid import UUID

from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.domain_event_publisher_port import DomainEventPublisherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.entities.lead import Lead
from domain.entities.sales_group import SalesGroup
from domain.value_objects.enums import LeadStatus
from domain.services.assignment_engine import AssignmentEngine
from domain.services.scoring_engine import ScoringEngine
from domain.exceptions import DomainException
from domain.events.lead_events import LeadProcessedEvent


class IngestLeadUseCase(IngestLeadInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        event_publisher: Optional[DomainEventPublisherPort] = None,
        engine: Optional[AssignmentEngine] = None,
        threshold_qualified: int = 30,
        threshold_disqualified: int = 0,
    ) -> None:
        self.uow = uow
        self.event_publisher = event_publisher
        self.scoring_engine = ScoringEngine()
        # The engine is stateless (the rotation cursor lives on the
        # persisted rule instead), so a private instance is exactly as
        # correct as a shared one; callers that do not care get one for free.
        self.engine = engine or AssignmentEngine()
        self.threshold_qualified = threshold_qualified
        self.threshold_disqualified = threshold_disqualified

    def execute(self, command: IngestLeadCommand) -> LeadProcessedResult:
        try:
            lead = Lead.create(
                tenant_id=command.tenant_id,
                first_name=command.first_name,
                last_name=command.last_name,
                email=command.email,
                company=command.company,
                budget=command.budget,
                industry=command.industry,
                custom_attributes=command.custom_attributes,
                phone=command.phone,
            )
        except DomainException as e:
            return LeadProcessedResult(
                lead_id="",
                status=LeadStatus.FAILED.value,
                score=0,
                error=str(e),
                error_code=e.error_code,
            )

        assigned_agent = None
        with self.uow:
            scoring_rules = self.uow.rules.get_scoring_rules_by_tenant(lead.tenant_id.value)
            breakdown = self.scoring_engine.evaluate(lead, scoring_rules)
            # The rules that produced a score can be edited or deleted later,
            # so the lead keeps its own record to be able to explain itself.
            lead.score_breakdown = breakdown.applied
            lead.qualify(self.threshold_qualified, self.threshold_disqualified)

            if lead.status == LeadStatus.QUALIFIED:
                assignment_rules = self.uow.rules.get_assignment_rules_by_tenant(lead.tenant_id.value)
                available_agents = self.uow.agents.get_available_agents(lead.tenant_id.value)
                groups_by_id: Dict[UUID, SalesGroup] = {
                    group.id.value: group
                    for group in self.uow.groups.list_by_tenant(lead.tenant_id.value, limit=10_000)
                }
                loads = self.uow.leads.active_load_by_agent(lead.tenant_id.value)

                cursors_before = {rule.id: rule.rr_cursor for rule in assignment_rules}
                assigned_agent = self.engine.select_agent(
                    lead, assignment_rules, available_agents, groups_by_id, loads
                )
                if assigned_agent is None:
                    # QUALIFIED and UNASSIGNED used to be indistinguishable, so
                    # a lead nobody could take looked like one not yet routed.
                    lead.leave_unassigned()
                # Only the rule the engine actually used can have rotated;
                # saving just that one avoids rewriting every rule per lead.
                for rule in assignment_rules:
                    if rule.rr_cursor != cursors_before[rule.id]:
                        self.uow.rules.save_assignment_rule(lead.tenant_id.value, rule)

            saved_lead = self.uow.leads.save(lead)

        if self.event_publisher:
            event = LeadProcessedEvent(
                tenant_id=str(saved_lead.tenant_id.value),
                lead_id=str(saved_lead.id),
                email=str(saved_lead.email),
                score=int(saved_lead.score),
                status=saved_lead.status,
                assigned_agent_id=str(assigned_agent.id) if assigned_agent else None,
            )
            self.event_publisher.publish(event)

        return LeadProcessedResult(
            lead_id=str(saved_lead.id),
            status=saved_lead.status.value,
            score=int(saved_lead.score),
            assigned_agent_id=str(assigned_agent.id) if assigned_agent else None,
            applied_rules_count=len(breakdown.applied),
            webhook_dispatched=True if self.event_publisher else False,
        )
