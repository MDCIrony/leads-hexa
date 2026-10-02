"""AdmitLeadUseCase: lead-core's decision, idempotent by (tenant_id, intake_record_id) (ADR-0035)."""
import uuid
from unittest.mock import MagicMock

import pytest

from application.dtos.admissions import AdmissionCandidate, AdmissionRequest
from application.ports.output.lead_repository_port import DuplicateAdmission
from application.use_cases.admissions.admit_lead import AdmitLeadUseCase
from domain.entities import AssignmentRule
from domain.entities.disqualification_rule import DisqualificationRule
from domain.entities.lead import Lead
from domain.value_objects.enums import Operator
from tests.unit.mocks.in_memory_advisor_repo import make_advisor
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _request(tenant_id=None, record_id=None, **candidate) -> AdmissionRequest:
    fields = dict(first_name="Jane", last_name="Doe", email="jane@example.com", phone=None,
                  company="Acme", industry="Tech", budget="5000.00", custom_attributes={})
    fields.update(candidate)
    return AdmissionRequest(tenant_id=tenant_id or uuid.uuid4(), intake_record_id=record_id or uuid.uuid4(),
                            source_id=uuid.uuid4(), candidate=AdmissionCandidate(**fields))


def _events(uow, channel: str) -> list:
    return [entry.event_type for entry in uow.outbox.list_unpublished(channel, 10)]


def test_a_new_candidate_becomes_an_assigned_lead_linked_to_its_record():
    uow = InMemoryUnitOfWork()
    tenant_id = uuid.uuid4()
    agent = uow.advisors.seed(make_advisor(name="Carlos", tenant_id=tenant_id))
    uow.rules.save_assignment_rule(tenant_id, AssignmentRule.create(
        tenant_id=tenant_id, name="Catch-all", target_agent_ids=[agent.id.value]))
    request = _request(tenant_id)

    result = AdmitLeadUseCase(uow).execute(request)

    assert (result.outcome, result.status, result.assigned_agent_id) == ("ADMITTED", "ASSIGNED", str(agent.id))
    lead = uow.leads.get_by_intake_record(tenant_id, request.intake_record_id)
    assert str(lead.id) == result.lead_id
    assert _events(uow, "product") == ["LeadProcessedEvent"]
    assert _events(uow, "internal") == ["LeadAssigned"]


def test_a_lead_nobody_can_take_is_left_unassigned_with_its_notice_in_the_outbox():
    uow = InMemoryUnitOfWork()

    result = AdmitLeadUseCase(uow).execute(_request())

    assert (result.outcome, result.status, result.assigned_agent_id) == ("ADMITTED", "UNASSIGNED", None)
    assert _events(uow, "internal") == ["LeadLeftUnassigned"]


def test_a_disqualified_candidate_publishes_only_its_disqualification_on_the_product_lane():
    uow = InMemoryUnitOfWork()
    tenant_id = uuid.uuid4()
    uow.disqualification_rules.save(DisqualificationRule.create(
        tenant_id=tenant_id, name="No way to contact",
        conditions=[{"field": "phone", "operator": Operator.IS_EMPTY.value}]))

    result = AdmitLeadUseCase(uow).execute(_request(tenant_id))

    assert (result.outcome, result.status, result.assigned_agent_id) == ("ADMITTED", "DISQUALIFIED", None)
    assert _events(uow, "product") == ["LeadDisqualified"]
    assert uow.outbox.list_unpublished("product", 10)[0].payload["reason"] == "No way to contact"
    assert _events(uow, "internal") == []


def test_a_record_already_admitted_returns_its_lead_as_it_is_now_and_publishes_nothing():
    uow = InMemoryUnitOfWork()
    request = _request()
    first = AdmitLeadUseCase(uow).execute(request)
    published = len(uow.outbox._entries)

    again = AdmitLeadUseCase(uow).execute(request)

    assert again == first
    assert len(uow.outbox._entries) == published
    assert len(uow.leads.leads) == 1


def test_an_invalid_candidate_is_rejected_without_writing_anything():
    uow = InMemoryUnitOfWork()

    result = AdmitLeadUseCase(uow).execute(_request(email="not-an-email"))

    assert result.outcome == "REJECTED"
    assert [(e.field, e.error_code) for e in result.errors] == [("email", "INVALID_EMAIL")]
    assert result.lead_id is None
    assert uow.leads.leads == {}
    assert uow.outbox._entries == {}


def test_an_unreadable_budget_is_a_rejection_not_an_error():
    result = AdmitLeadUseCase(InMemoryUnitOfWork()).execute(_request(budget="nine thousand"))

    assert [(e.field, e.error_code) for e in result.errors] == [("budget", "INVALID_BUDGET")]


def test_the_loser_of_a_race_rolls_back_and_answers_with_the_winners_lead():
    """The pre-check missed it; the unique constraint did not."""
    tenant_id, record_id = uuid.uuid4(), uuid.uuid4()
    winner = Lead.create(tenant_id=tenant_id, source_id=uuid.uuid4(), first_name="W", last_name="W",
                         company="W", budget="10", industry="W", intake_record_id=record_id)

    class _RacedLeads(InMemoryLeadRepository):
        def save(self, lead):
            self.leads[winner.id.value] = winner
            raise DuplicateAdmission(str(record_id))

    uow = InMemoryUnitOfWork(leads=_RacedLeads())

    result = AdmitLeadUseCase(uow).execute(_request(tenant_id, record_id))

    assert (result.outcome, result.lead_id) == ("ADMITTED", str(winner.id))
    assert uow.outbox._entries == {}


def test_a_persistence_failure_rolls_the_decision_back():
    uow = MagicMock()
    uow.__enter__.return_value = uow

    def _exit(exc_type, *_):
        uow.rollback() if exc_type else uow.commit()
        return False

    uow.__exit__.side_effect = _exit
    uow.leads.get_by_intake_record.return_value = None
    uow.rules.get_scoring_rules_by_tenant.return_value = []
    uow.rules.lock_assignment_rules_by_tenant.return_value = []
    uow.disqualification_rules.list_by_tenant.return_value = []
    uow.advisors.list_available.return_value = []
    uow.groups.list_by_tenant.return_value = []
    uow.leads.active_load_by_agent.return_value = {}
    uow.leads.save.side_effect = Exception("Database failure")

    with pytest.raises(Exception, match="Database failure"):
        AdmitLeadUseCase(uow).execute(_request())

    uow.rollback.assert_called_once()
    uow.commit.assert_not_called()


def test_the_events_belong_to_the_transaction_of_the_lead():
    """A refused commit takes the outbox rows with it: a notice about a lead
    that was rolled back would point at nothing."""

    class _CommitFails(InMemoryUnitOfWork):
        def commit(self) -> None:
            self.rollback()
            raise RuntimeError("commit refused")

    uow = _CommitFails()

    with pytest.raises(RuntimeError):
        AdmitLeadUseCase(uow).execute(_request())

    assert uow.outbox._entries == {}


def test_a_missing_required_text_field_is_rejected_before_the_database():
    uow = InMemoryUnitOfWork()

    result = AdmitLeadUseCase(uow).execute(_request(first_name=None, industry=None))

    assert result.outcome == "REJECTED"
    assert [(e.field, e.error_code) for e in result.errors] == [
        ("first_name", "MISSING_REQUIRED_FIELD"), ("industry", "MISSING_REQUIRED_FIELD")]
    assert uow.leads.leads == {}
    assert uow.outbox._entries == {}
