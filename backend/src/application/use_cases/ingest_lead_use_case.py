from typing import Optional
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.agent_repository_port import AgentRepositoryPort
from application.ports.output.domain_event_publisher_port import DomainEventPublisherPort
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.entities.lead import Lead
from domain.value_objects.enums import LeadStatus
from domain.services.scoring_engine import ScoringEngine
from domain.services.router_engine import RouterEngine
from domain.exceptions import DomainException
from domain.events.lead_events import LeadProcessedEvent


class IngestLeadUseCase(IngestLeadInputPort):
    def __init__(
        self,
        uow: Optional[UnitOfWorkPort] = None,
        lead_repo: Optional[LeadRepositoryPort] = None,
        rule_repo: Optional[RuleRepositoryPort] = None,
        agent_repo: Optional[AgentRepositoryPort] = None,
        event_publisher: Optional[DomainEventPublisherPort] = None,
        threshold_qualified: int = 30,
        threshold_disqualified: int = 0,
    ) -> None:
        self.uow = uow
        self.lead_repo = lead_repo
        self.rule_repo = rule_repo
        self.agent_repo = agent_repo
        self.event_publisher = event_publisher
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
                error_code=e.error_code,
            )

        if self.uow:
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
        else:
            rule_repo = self.rule_repo
            agent_repo = self.agent_repo
            lead_repo = self.lead_repo

            scoring_rules = rule_repo.get_scoring_rules_by_tenant(lead.tenant_id.value) if rule_repo else []
            self.scoring_engine.evaluate(lead, scoring_rules)
            lead.qualify(self.threshold_qualified, self.threshold_disqualified)

            assigned_agent = None
            if lead.status == LeadStatus.QUALIFIED and agent_repo:
                routing_rules = rule_repo.get_routing_rules_by_tenant(lead.tenant_id.value) if rule_repo else []
                available_agents = agent_repo.get_available_agents()
                assigned_agent = self.router_engine.select_agent(lead, routing_rules, available_agents)
                if assigned_agent:
                    agent_repo.update_active_count(
                        assigned_agent.id.value,
                        assigned_agent.active_leads_count + 1
                    )

            saved_lead = lead_repo.save(lead) if lead_repo else lead

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
            applied_rules_count=len(scoring_rules),
            webhook_dispatched=True if self.event_publisher else False,
        )
