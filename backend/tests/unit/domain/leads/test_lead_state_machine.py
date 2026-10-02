import uuid
from typing import Optional

import pytest

from domain.leads.lead import Lead
from domain.exceptions import DomainException
from domain.value_objects.enums import LeadStatus

_TENANT = uuid.uuid4()


def _lead(status: LeadStatus = LeadStatus.QUALIFIED, tenant_id: Optional[uuid.UUID] = None) -> Lead:
    return Lead.create(
        tenant_id=tenant_id or _TENANT, source_id=uuid.uuid4(), first_name="Ana", last_name="Diaz",
        email="ana@x.test", company="C", budget=100, industry="tech", status=status,
    )


class TestAssign:
    def test_assigning_a_qualified_lead_records_the_moment(self):
        lead = _lead(LeadStatus.QUALIFIED)
        agent = uuid.uuid4()

        lead.assign_to(agent, _TENANT)

        assert lead.status == LeadStatus.ASSIGNED
        assert lead.assigned_agent_id is not None
        assert lead.assigned_agent_id.value == agent
        assert lead.assigned_at is not None

    def test_an_unassigned_lead_can_be_assigned_by_hand(self):
        lead = _lead(LeadStatus.UNASSIGNED)
        lead.assign_to(uuid.uuid4(), _TENANT)
        assert lead.status == LeadStatus.ASSIGNED

    def test_a_disqualified_lead_cannot_be_assigned(self):
        """The engine must never reach it, and neither may the manager."""
        lead = _lead(LeadStatus.DISQUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.assign_to(uuid.uuid4(), _TENANT)
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"

    def test_assigning_an_already_assigned_lead_is_refused(self):
        """Overwriting in silence is what reassign_to exists to prevent."""
        lead = _lead(LeadStatus.QUALIFIED)
        lead.assign_to(uuid.uuid4(), _TENANT)
        with pytest.raises(DomainException) as exc:
            lead.assign_to(uuid.uuid4(), _TENANT)
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"

    def test_an_agent_of_another_organization_is_refused(self):
        lead = _lead(LeadStatus.QUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.assign_to(uuid.uuid4(), uuid.uuid4())
        assert exc.value.error_code == "CROSS_TENANT_ASSIGNMENT"


class TestReassign:
    def test_reassigning_replaces_the_agent_and_the_moment(self):
        lead = _lead(LeadStatus.QUALIFIED)
        first, second = uuid.uuid4(), uuid.uuid4()
        lead.assign_to(first, _TENANT)
        first_at = lead.assigned_at

        lead.reassign_to(second, _TENANT)

        assert lead.assigned_agent_id.value == second
        assert lead.assigned_at >= first_at

    def test_reassigning_something_never_assigned_is_refused(self):
        lead = _lead(LeadStatus.QUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.reassign_to(uuid.uuid4(), _TENANT)
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"


class TestUnassignAndDiscard:
    def test_releasing_an_assigned_lead_clears_the_agent(self):
        lead = _lead(LeadStatus.QUALIFIED)
        lead.assign_to(uuid.uuid4(), _TENANT)

        lead.unassign()

        assert lead.status == LeadStatus.UNASSIGNED
        assert lead.assigned_agent_id is None
        assert lead.assigned_at is None

    def test_discarding_requires_a_reason(self):
        lead = _lead(LeadStatus.QUALIFIED)
        with pytest.raises(DomainException) as exc:
            lead.discard("   ")
        assert exc.value.error_code == "DISCARD_WITHOUT_REASON"

    def test_a_lead_can_be_discarded_from_any_live_state(self):
        for status in (LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.UNASSIGNED, LeadStatus.ASSIGNED):
            lead = _lead(status)
            lead.discard("duplicado")
            assert lead.status == LeadStatus.DISCARDED
            assert lead.discard_reason == "duplicado"

    def test_discarding_twice_is_refused(self):
        lead = _lead(LeadStatus.QUALIFIED)
        lead.discard("duplicado")
        with pytest.raises(DomainException) as exc:
            lead.discard("otra vez")
        assert exc.value.error_code == "INVALID_LEAD_TRANSITION"

    def test_a_qualified_lead_with_no_candidate_is_left_unassigned(self):
        lead = _lead(LeadStatus.QUALIFIED)
        lead.leave_unassigned()
        assert lead.status == LeadStatus.UNASSIGNED
