import uuid

import pytest

from domain.exceptions import InvalidUUIDException
from domain.value_objects.agent_role import AgentRole
from domain.value_objects.intake_job_id import IntakeJobId
from domain.value_objects.intake_record_id import IntakeRecordId
from domain.value_objects.lead_id import LeadId
from domain.value_objects.lead_source_id import LeadSourceId
from domain.value_objects.tenant_id import TenantId

_IDENTIFIERS = [IntakeJobId, IntakeRecordId, LeadId, LeadSourceId, TenantId]


@pytest.mark.parametrize("identifier", _IDENTIFIERS)
def test_an_identifier_is_generated_when_none_is_given(identifier):
    assert isinstance(identifier().value, uuid.UUID)


@pytest.mark.parametrize("identifier", _IDENTIFIERS)
def test_an_identifier_parses_a_string_and_prints_it_back(identifier):
    raw = str(uuid.uuid4())
    assert str(identifier(raw)) == raw


@pytest.mark.parametrize("identifier", _IDENTIFIERS)
@pytest.mark.parametrize("value", ["not-a-uuid", 42])
def test_an_invalid_identifier_is_rejected(identifier, value):
    with pytest.raises(InvalidUUIDException):
        identifier(value)


def test_agent_role_is_the_closed_set_the_token_can_carry():
    assert {r.value for r in AgentRole} == {"ADMIN", "MANAGER", "AGENT", "INTEGRATION"}
