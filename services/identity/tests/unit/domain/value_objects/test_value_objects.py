import uuid

import pytest

from domain.exceptions import InvalidUUIDException
from domain.value_objects.agent_id import AgentId
from domain.value_objects.agent_role import AgentRole
from domain.value_objects.tenant_id import TenantId


@pytest.mark.parametrize("identifier", [AgentId, TenantId])
def test_an_identifier_is_generated_when_none_is_given(identifier):
    assert isinstance(identifier().value, uuid.UUID)


@pytest.mark.parametrize("identifier", [AgentId, TenantId])
def test_an_identifier_parses_a_string_and_prints_it_back(identifier):
    raw = str(uuid.uuid4())
    assert str(identifier(raw)) == raw


@pytest.mark.parametrize("identifier", [AgentId, TenantId])
@pytest.mark.parametrize("value", ["not-a-uuid", 42])
def test_an_invalid_identifier_is_rejected(identifier, value):
    with pytest.raises(InvalidUUIDException):
        identifier(value)


def test_agent_role_has_exactly_four_members():
    # INTEGRATION added for the machine credential (ADR-0028): a closed set
    # gaining a value, not a type change.
    assert {r.value for r in AgentRole} == {"ADMIN", "MANAGER", "AGENT", "INTEGRATION"}


def test_agent_role_is_string_enum():
    assert AgentRole.ADMIN == "ADMIN"
    assert isinstance(AgentRole.ADMIN.value, str)
