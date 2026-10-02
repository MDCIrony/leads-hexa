"""lead-core's half of an ingestion: decide what a candidate becomes (ADR-0035).

Knows nothing of intake records beyond their id: claiming and closing the
record is intake's half, which reaches this one over /internal/v1/admissions."""
from typing import Dict, Optional
from uuid import UUID

from application.dtos.admissions import AdmissionError, AdmissionRequest, AdmissionResult
from application.ports.input.admissions.admission_ports import AdmitLeadInputPort
from application.ports.output.lead_repository_port import DuplicateAdmission
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.lead import Lead
from domain.entities.sales_group import SalesGroup
from domain.events.lead_events import LeadAssigned, LeadDisqualified, LeadLeftUnassigned, LeadProcessedEvent
from domain.exceptions import DomainException
from domain.services.assignment_engine import AssignmentEngine
from domain.services.scoring_engine import ScoringEngine
from domain.services.viability_engine import ViabilityEngine
from domain.value_objects.enums import LeadStatus

# Verified against domain/exceptions.py: these are the codes the entity's
# value objects actually raise. Do not invent new ones.
_FIELD_BY_ERROR_CODE = {
    "INVALID_EMAIL": "email",
    "INVALID_BUDGET": "budget",
    "INVALID_UUID": "_record",
}
# NOT NULL in leads: a null here must be a deterministic REJECTED, not a
# database error the caller would retry forever.
_REQUIRED_TEXT = ("first_name", "last_name", "company", "industry")


class AdmitLeadUseCase(AdmitLeadInputPort):
    def __init__(self, uow: UnitOfWorkPort, engine: Optional[AssignmentEngine] = None) -> None:
        self.uow = uow
        self.scoring_engine = ScoringEngine()
        self.viability_engine = ViabilityEngine()
        # Stateless (the rotation cursor lives on the persisted rule), so a
        # private instance is as correct as a shared one.
        self.engine = engine or AssignmentEngine()

    def execute(self, request: AdmissionRequest) -> AdmissionResult:
        try:
            with self.uow:
                # Checked first so a redelivery does not run the engines again;
                # the unique constraint is what covers two calls at once.
                existing = self.uow.leads.get_by_intake_record(request.tenant_id, request.intake_record_id)
                if existing is not None:
                    return _admitted(existing)
                missing = tuple(
                    AdmissionError(field=name, message=f"{name} is required", error_code="MISSING_REQUIRED_FIELD")
                    for name in _REQUIRED_TEXT if getattr(request.candidate, name) is None)
                if missing:
                    return AdmissionResult(outcome="REJECTED", errors=missing)
                try:
                    lead = _lead_of(request)
                except DomainException as exc:
                    # Nothing is written, and Lead.create is deterministic: a
                    # repeated call gets the same answer.
                    field = _FIELD_BY_ERROR_CODE.get(exc.error_code, "_record")
                    return AdmissionResult(outcome="REJECTED", errors=(
                        AdmissionError(field=field, message=str(exc), error_code=exc.error_code),))
                return _admitted(self._decide(lead))
        except DuplicateAdmission:
            # The losing transaction is gone, cursor advance included; the
            # winner's lead is the answer, read in a transaction of its own.
            with self.uow:
                winner = self.uow.leads.get_by_intake_record(request.tenant_id, request.intake_record_id)
            if winner is None:
                raise
            return _admitted(winner)

    def _decide(self, lead: Lead) -> Lead:
        tenant_id = lead.tenant_id.value
        # Viability runs first and cuts the flow: scoring and routing
        # something nobody can work is wasted work with a misleading result.
        breached = self.viability_engine.evaluate(
            lead, self.uow.disqualification_rules.list_by_tenant(tenant_id, limit=10_000))
        if breached is not None:
            lead.disqualify(breached.name)
        else:
            # The rules that produced a score can be edited or deleted later,
            # so the lead keeps its own record to explain itself.
            lead.score_breakdown = self.scoring_engine.evaluate(
                lead, self.uow.rules.get_scoring_rules_by_tenant(tenant_id)).applied
            lead.qualify()
            self._route(lead)
        saved = self.uow.leads.save(lead)
        # Registered inside the transaction, not published after it
        # (ADR-0025): a rollback must take the outbound facts with it.
        self.uow.outbox.record(
            LeadDisqualified(tenant_id=str(tenant_id), lead_id=str(saved.id), source_id=str(saved.source_id.value),
                             reason=saved.disqualification_reason or "")
            if saved.status == LeadStatus.DISQUALIFIED else LeadProcessedEvent.of(saved))
        if saved.status == LeadStatus.ASSIGNED:
            self.uow.outbox.record(LeadAssigned(
                tenant_id=str(tenant_id), lead_id=str(saved.id), agent_id=str(saved.assigned_agent_id)),
                channel="internal")
        elif saved.status == LeadStatus.UNASSIGNED:
            self.uow.outbox.record(LeadLeftUnassigned(tenant_id=str(tenant_id), lead_id=str(saved.id)),
                                   channel="internal")
        return saved

    def _route(self, lead: Lead) -> None:
        tenant_id = lead.tenant_id.value
        # Locked, not just read: this advances the rotation cursor, and a
        # plain read lets a concurrent admission overwrite the increment.
        assignment_rules = self.uow.rules.lock_assignment_rules_by_tenant(tenant_id)
        groups_by_id: Dict[UUID, SalesGroup] = {
            group.id.value: group for group in self.uow.groups.list_by_tenant(tenant_id, limit=10_000)}
        cursors_before = {rule.id: rule.rr_cursor for rule in assignment_rules}
        agent = self.engine.select_agent(lead, assignment_rules, self.uow.advisors.list_available(tenant_id),
                                         groups_by_id, self.uow.leads.active_load_by_agent(tenant_id))
        if agent is None:
            # QUALIFIED and UNASSIGNED used to be indistinguishable, so a lead
            # nobody could take looked like one not yet routed.
            lead.leave_unassigned()
        # Only the rule the engine used can have rotated; saving just that one
        # avoids rewriting every rule per lead.
        for rule in assignment_rules:
            if rule.rr_cursor != cursors_before[rule.id]:
                self.uow.rules.save_assignment_rule(tenant_id, rule)


def _lead_of(request: AdmissionRequest) -> Lead:
    candidate = request.candidate
    return Lead.create(
        tenant_id=request.tenant_id, source_id=request.source_id, first_name=candidate.first_name,
        last_name=candidate.last_name, email=candidate.email, company=candidate.company,
        budget=candidate.budget, industry=candidate.industry, custom_attributes=candidate.custom_attributes,
        phone=candidate.phone, intake_record_id=request.intake_record_id,
    )


def _admitted(lead: Lead) -> AdmissionResult:
    """The lead as it is now, whether just decided or decided by an earlier call."""
    return AdmissionResult(
        outcome="ADMITTED", lead_id=str(lead.id), status=lead.status.value, score=int(lead.score),
        assigned_agent_id=str(lead.assigned_agent_id) if lead.assigned_agent_id else None,
        applied_rules_count=len(lead.score_breakdown),
    )
