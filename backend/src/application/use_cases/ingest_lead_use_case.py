from typing import Optional
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.agent_repository_port import AgentRepositoryPort
from application.ports.output.webhook_dispatcher_port import WebhookDispatcherPort
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.entities.lead import Lead
from domain.value_objects import (
    LeadId,
    TenantId,
    EmailAddress,
    Money,
    LeadStatus,
)
from domain.services.scoring_engine import ScoringEngine
from domain.services.router_engine import RouterEngine
from domain.exceptions import DomainException

class IngestLeadUseCase(IngestLeadInputPort):
    def __init__(
        self,
        lead_repo: LeadRepositoryPort,
        rule_repo: RuleRepositoryPort,
        agent_repo: AgentRepositoryPort,
        webhook_dispatcher: Optional[WebhookDispatcherPort] = None,
        threshold_qualified: int = 30,
        threshold_disqualified: int = 0,
    ) -> None:
        self.lead_repo = lead_repo
        self.rule_repo = rule_repo
        self.agent_repo = agent_repo
        self.webhook_dispatcher = webhook_dispatcher
        self.scoring_engine = ScoringEngine()
        self.router_engine = RouterEngine()
        self.threshold_qualified = threshold_qualified
        self.threshold_disqualified = threshold_disqualified

    def execute(self, command: IngestLeadCommand) -> LeadProcessedResult:
        try:
            email_vo = EmailAddress(command.email)
            money_vo = Money(command.budget)
            tenant_id_vo = TenantId(command.tenant_id)
            lead_id_vo = LeadId()

            lead = Lead(
                id=lead_id_vo,
                tenant_id=tenant_id_vo,
                first_name=command.first_name,
                last_name=command.last_name,
                email=email_vo,
                company=command.company,
                budget=money_vo,
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

        # 1. Scoring Engine
        scoring_rules = self.rule_repo.get_scoring_rules_by_tenant(tenant_id_vo.value)
        self.scoring_engine.evaluate(lead, scoring_rules)
        lead.qualify(self.threshold_qualified, self.threshold_disqualified)

        # 2. Router Engine (si es QUALIFIED)
        assigned_agent = None
        if lead.status == LeadStatus.QUALIFIED:
            routing_rules = self.rule_repo.get_routing_rules_by_tenant(tenant_id_vo.value)
            available_agents = self.agent_repo.get_available_agents()
            assigned_agent = self.router_engine.select_agent(lead, routing_rules, available_agents)
            if assigned_agent:
                self.agent_repo.update_active_count(
                    assigned_agent.id.value,
                    assigned_agent.active_leads_count + 1
                )

        # 3. Persistence
        saved_lead = self.lead_repo.save(lead)

        # 4. Webhook Dispatch
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
