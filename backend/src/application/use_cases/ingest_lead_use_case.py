from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.domain_event_publisher_port import DomainEventPublisherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.entities.intake_record import IntakeError, IntakeRecord
from domain.entities.lead import Lead
from domain.entities.sales_group import SalesGroup
from domain.value_objects.enums import IntakeRecordStatus, LeadSourceKind, LeadStatus
from domain.services.assignment_engine import AssignmentEngine
from domain.services.scoring_engine import ScoringEngine
from domain.exceptions import DomainException
from domain.events.lead_events import LeadProcessedEvent

# Verified against domain/exceptions.py: these are the codes the entity's
# value objects actually raise. Do not invent new ones.
_FIELD_BY_ERROR_CODE = {
    "INVALID_EMAIL": "email",
    "INVALID_BUDGET": "budget",
    "INVALID_UUID": "_record",
}


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

    def resolve_source_id(self, tenant_id: UUID, kind: LeadSourceKind) -> UUID:
        """Looks up the tenant's active source for this channel. Every tenant
        gets a MANUAL_FORM and a FILE_UPLOAD source at creation time
        (CreateTenantUseCase), so a miss here means the catalog is missing an
        entry, not that the caller sent a bad request."""
        with self.uow:
            source = self.uow.sources.get_by_kind(tenant_id, kind)
        if source is None:
            raise DomainException(
                f"No active source of kind {kind.value} found for this organization",
                error_code="SOURCE_NOT_FOUND",
            )
        return source.id.value

    def execute(
        self,
        command: IngestLeadCommand,
        existing_record: Optional[IntakeRecord] = None,
    ) -> LeadProcessedResult:
        assigned_agent = None
        with self.uow:
            # Promotion reuses the row the manager is correcting instead of
            # opening another one: the inbox should show one attempt per
            # payload, not one per retry. First-time ingestion has no such
            # row yet, so it persists a new one before Lead.create is
            # attempted — a payload that fails validation must not vanish.
            record = existing_record or self.uow.intake_records.save(
                IntakeRecord.create(
                    tenant_id=command.tenant_id,
                    source_id=command.source_id,
                    payload=payload_of(command),
                )
            )

            try:
                lead = Lead.create(
                    tenant_id=command.tenant_id,
                    source_id=command.source_id,
                    first_name=command.first_name,
                    last_name=command.last_name,
                    email=command.email,
                    company=command.company,
                    budget=command.budget,
                    industry=command.industry,
                    custom_attributes=command.custom_attributes,
                    phone=command.phone,
                )
            except DomainException as exc:
                record.reject([IntakeError(
                    field=self._field_of(exc),
                    message=str(exc),
                    error_code=exc.error_code,
                )])
                self.uow.intake_records.save(record)
                return LeadProcessedResult(
                    lead_id="",
                    intake_record_id=str(record.id),
                    status=IntakeRecordStatus.REJECTED.value,
                    score=0,
                    error=str(exc),
                    error_code=exc.error_code,
                )

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
            record.promote(saved_lead.id)
            self.uow.intake_records.save(record)

        if self.event_publisher:
            event = LeadProcessedEvent(
                tenant_id=str(saved_lead.tenant_id.value),
                lead_id=str(saved_lead.id),
                email=str(saved_lead.email) if saved_lead.email else None,
                score=int(saved_lead.score),
                status=saved_lead.status,
                assigned_agent_id=str(assigned_agent.id) if assigned_agent else None,
            )
            self.event_publisher.publish(event)

        return LeadProcessedResult(
            lead_id=str(saved_lead.id),
            intake_record_id=str(record.id),
            status=saved_lead.status.value,
            score=int(saved_lead.score),
            assigned_agent_id=str(assigned_agent.id) if assigned_agent else None,
            applied_rules_count=len(breakdown.applied),
            webhook_dispatched=True if self.event_publisher else False,
        )

    @staticmethod
    def _field_of(exc: DomainException) -> str:
        # Falls back to "_record" (the payload as a whole) for any error code
        # not in the map above, rather than guessing a field that isn't real.
        return _FIELD_BY_ERROR_CODE.get(exc.error_code, "_record")


def payload_of(command: IngestLeadCommand) -> Dict[str, Any]:
    """Snapshot the raw command into a JSONB-serializable dict.

    Must not raise on a malformed value (e.g. a non-numeric budget): this
    runs before Lead.create, so it cannot re-run the validation that is
    about to happen and reject something the domain hasn't judged yet."""
    budget = command.budget
    return {
        "tenant_id": str(command.tenant_id),
        "source_id": str(command.source_id),
        "first_name": command.first_name,
        "last_name": command.last_name,
        "company": command.company,
        "budget": float(budget) if isinstance(budget, Decimal) else budget,
        "industry": command.industry,
        "custom_attributes": command.custom_attributes,
        "phone": command.phone,
        "email": command.email,
    }


def command_from_record(record: IntakeRecord) -> IngestLeadCommand:
    """Rebuild the command from what was stored, without re-validating it.

    tenant_id and source_id come from the record, never from the payload: the
    organization is the one that was authenticated at reception (C4), and the
    payload is untrusted input that happens to carry a copy of both."""
    payload = record.payload or {}
    return IngestLeadCommand(
        tenant_id=record.tenant_id.value,
        source_id=record.source_id.value,
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        company=payload.get("company"),
        budget=payload.get("budget"),
        industry=payload.get("industry"),
        custom_attributes=payload.get("custom_attributes") or {},
        phone=payload.get("phone"),
        email=payload.get("email"),
    )
