from typing import Optional
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.ports.output.webhook_dispatcher_port import WebhookDispatcherPort
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.entities.lead import Lead
from domain.value_objects.enums import LeadStatus
from domain.services.scoring_engine import ScoringEngine
from domain.services.router_engine import RouterEngine
from domain.exceptions import DomainException

class IngestLeadUseCase(IngestLeadInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        webhook_dispatcher: Optional[WebhookDispatcherPort] = None,
        threshold_qualified: int = 30,
        threshold_disqualified: int = 0,
    ) -> None:
        self.uow = uow
        self.webhook_dispatcher = webhook_dispatcher
        self.scoring_engine = ScoringEngine()
        self.router_engine = RouterEngine()
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
            )

        with self.uow:
            scoring_rules = self.uow.rules.get_scoring_rules_by_tenant(lead.tenant_id.value)
            self.scoring_engine.evaluate(lead, scoring_rules)
            lead.qualify(self.threshold_qualified, self.threshold_disqualified)

            assigned_agent = None
            if lead.status == LeadStatus.QUALIFIED:
                routing_rules = self.uow.rules.get_routing_rules_by_tenant(lead.tenant_id.value)
                available_agents = self.uow.agents.get_available_agents()
                assigned_agent = self.router_engine.select_agent(lead, routing_rules, available_agents)
                if assigned_agent:
                    self.uow.agents.update_active_count(
                        assigned_agent.id.value,
                        assigned_agent.active_leads_count + 1
                    )

            saved_lead = self.uow.leads.save(lead)

        dispatched = False

        if self.webhook_dispatcher:
            payload = {
                "lead_id": str(saved_lead.id),
                "email": str(saved_lead.email),
                "score": int(saved_lead.score),
                "status": saved_lead.status.value,
            }
            dispatched = self.webhook_dispatcher.dispatch(
                target_url="https://hooks.user.com/lead",
                secret_token="secret",
                payload=payload,
            )

        return LeadProcessedResult(
            lead_id=str(saved_lead.id),
            status=saved_lead.status.value,
            score=int(saved_lead.score),
            assigned_agent_id=str(assigned_agent.id) if assigned_agent else None,
            applied_rules_count=len(scoring_rules),
            webhook_dispatched=dispatched,
        )
