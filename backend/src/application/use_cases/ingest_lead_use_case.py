import math
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.entities.intake_record import IntakeError, IntakeRecord
from domain.entities.lead import Lead
from domain.entities.sales_group import SalesGroup
from domain.value_objects.enums import IntakeRecordStatus, LeadSourceKind, LeadStatus
from domain.value_objects.score_breakdown import ScoreBreakdown
from domain.services.assignment_engine import AssignmentEngine
from domain.services.scoring_engine import ScoringEngine
from domain.services.viability_engine import ViabilityEngine
from domain.exceptions import DomainException
from domain.events.intake_events import IntakeRejected
from domain.events.lead_events import LeadAssigned, LeadDisqualified, LeadLeftUnassigned, LeadProcessedEvent

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
        engine: Optional[AssignmentEngine] = None,
    ) -> None:
        self.uow = uow
        self.scoring_engine = ScoringEngine()
        self.viability_engine = ViabilityEngine()
        # The engine is stateless (the rotation cursor lives on the
        # persisted rule instead), so a private instance is exactly as
        # correct as a shared one; callers that do not care get one for free.
        self.engine = engine or AssignmentEngine()

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

    def execute(self, command: IngestLeadCommand, existing_record: IntakeRecord) -> LeadProcessedResult:
        assigned_agent = None
        left_unassigned = False
        with self.uow:
            # The record always exists by now: ReceiveIntakeUseCase (or the
            # batch pipeline) persisted it on arrival, so this use case only
            # ever marks what already landed — it no longer creates rows.
            # Claimed rather than trusted: whoever calls this may be racing
            # another run over the same job, and the loser has to find out
            # here, before it builds a second lead out of the same payload.
            record = self.uow.intake_records.claim_unpromoted(
                existing_record.id.value, command.tenant_id
            )
            if record is None:
                # Read inside this same transaction: opening a second one from
                # in here would nest the unit of work, which it does not model.
                return self._already_promoted(self.uow.intake_records.get_by_id_and_tenant(
                    existing_record.id.value, command.tenant_id
                ) or existing_record)

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
                self.uow.outbox.record(IntakeRejected(
                    tenant_id=str(record.tenant_id.value),
                    intake_record_id=str(record.id),
                    reason=str(exc),
                ), channel="internal")
                return LeadProcessedResult(
                    lead_id="",
                    intake_record_id=str(record.id),
                    status=IntakeRecordStatus.REJECTED.value,
                    score=0,
                    error=str(exc),
                    error_code=exc.error_code,
                )
            else:
                # Viability runs first and cuts the flow: scoring and routing
                # something nobody can work is wasted work with a misleading result.
                breakdown = ScoreBreakdown(applied=[], total=0)
                breached = self.viability_engine.evaluate(
                    lead, self.uow.disqualification_rules.list_by_tenant(lead.tenant_id.value, limit=10_000)
                )
                if breached is not None:
                    lead.disqualify(breached.name)
                else:
                    scoring_rules = self.uow.rules.get_scoring_rules_by_tenant(lead.tenant_id.value)
                    breakdown = self.scoring_engine.evaluate(lead, scoring_rules)
                    # The rules that produced a score can be edited or deleted
                    # later, so the lead keeps its own record to explain itself.
                    lead.score_breakdown = breakdown.applied
                    lead.qualify()

                    if lead.status == LeadStatus.QUALIFIED:
                        # Locked, not just read: this branch advances the
                        # rotation cursor, and a plain read lets a concurrent
                        # ingestion overwrite the increment.
                        assignment_rules = self.uow.rules.lock_assignment_rules_by_tenant(lead.tenant_id.value)
                        available_agents = self.uow.advisors.list_available(lead.tenant_id.value)
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
                            # QUALIFIED and UNASSIGNED used to be indistinguishable,
                            # so a lead nobody could take looked like one not yet routed.
                            lead.leave_unassigned()
                            left_unassigned = True
                        # Only the rule the engine actually used can have rotated;
                        # saving just that one avoids rewriting every rule per lead.
                        for rule in assignment_rules:
                            if rule.rr_cursor != cursors_before[rule.id]:
                                self.uow.rules.save_assignment_rule(lead.tenant_id.value, rule)

                saved_lead = self.uow.leads.save(lead)
                record.promote(saved_lead.id)
                self.uow.intake_records.save(record)
                # Registered inside the transaction, not published after it
                # (ADR-0025): a rollback must take the outbound fact with it.
                self.uow.outbox.record(
                    LeadDisqualified(
                        tenant_id=str(saved_lead.tenant_id.value),
                        lead_id=str(saved_lead.id),
                        source_id=str(saved_lead.source_id.value),
                        reason=saved_lead.disqualification_reason or "",
                    ) if saved_lead.status == LeadStatus.DISQUALIFIED
                    else LeadProcessedEvent.of(saved_lead)
                )
                # Same transaction, same reason: a notice about a lead that
                # was rolled back would point at nothing.
                if assigned_agent is not None:
                    self.uow.outbox.record(LeadAssigned(
                        tenant_id=str(saved_lead.tenant_id.value),
                        lead_id=str(saved_lead.id),
                        agent_id=str(assigned_agent.id),
                    ), channel="internal")
                elif left_unassigned:
                    self.uow.outbox.record(LeadLeftUnassigned(
                        tenant_id=str(saved_lead.tenant_id.value),
                        lead_id=str(saved_lead.id),
                    ), channel="internal")

        return LeadProcessedResult(
            lead_id=str(saved_lead.id),
            intake_record_id=str(record.id),
            status=saved_lead.status.value,
            score=int(saved_lead.score),
            assigned_agent_id=str(assigned_agent.id) if assigned_agent else None,
            applied_rules_count=len(breakdown.applied),
        )

    @staticmethod
    def _already_promoted(record: IntakeRecord) -> LeadProcessedResult:
        """Another run got here first. Report its lead, publish nothing.

        Returning the winner's identifier rather than an error is what keeps a
        redelivered message idempotent: the caller sees the same answer it
        would have got had it won the race."""
        return LeadProcessedResult(
            lead_id=str(record.lead_id.value) if record.lead_id else "",
            intake_record_id=str(record.id),
            status=IntakeRecordStatus.PROMOTED.value,
            score=0,
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
    if isinstance(budget, Decimal):
        budget = float(budget)
    # NaN and ±Infinity are the two values json.dumps turns into bare tokens
    # Postgres refuses as JSONB, which would fail the insert of a whole batch
    # over one bad cell. The record must persist even when its budget is
    # unusable; the domain rejects it on the next phase, with the field named.
    if isinstance(budget, float) and not math.isfinite(budget):
        budget = None
    return {
        "tenant_id": str(command.tenant_id),
        "source_id": str(command.source_id),
        "first_name": command.first_name,
        "last_name": command.last_name,
        "company": command.company,
        "budget": budget,
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
