import pytest
import uuid
from domain.value_objects import (
    EmailAddress,
    Money,
    LeadId,
    TenantId,
    AgentId,
    Score,
    AgentRole,
)
from domain.exceptions import (
    InvalidEmailException,
    InvalidBudgetException,
    InvalidUUIDException,
)

def test_email_address_valid():
    email = EmailAddress("valid.user@example.com")
    assert str(email) == "valid.user@example.com"

def test_email_address_invalid():
    with pytest.raises(InvalidEmailException):
        EmailAddress("invalid-email-format")

def test_money_valid():
    m = Money(15000.50)
    assert float(m) == 15000.50
    assert str(m) == "15000.50"

def test_money_invalid_negative():
    with pytest.raises(InvalidBudgetException):
        Money(-100)

def test_uuid_value_objects_generation():
    lead_id = LeadId()
    tenant_id = TenantId()
    agent_id = AgentId()

    assert isinstance(lead_id.value, uuid.UUID)
    assert isinstance(tenant_id.value, uuid.UUID)
    assert isinstance(agent_id.value, uuid.UUID)

def test_uuid_value_objects_parsing():
    raw_uuid = str(uuid.uuid4())
    lead_id = LeadId(raw_uuid)
    assert str(lead_id) == raw_uuid

def test_uuid_value_objects_invalid():
    with pytest.raises(InvalidUUIDException):
        LeadId("not-a-uuid")

def test_score_operations():
    score = Score(10)
    score = score.add_points(25)
    assert int(score) == 35

    score = score.subtract_points(10)
    assert int(score) == 25


def test_agent_role_has_exactly_three_members():
    assert {r.value for r in AgentRole} == {"ADMIN", "MANAGER", "AGENT"}


def test_agent_role_is_string_enum():
    assert AgentRole.ADMIN == "ADMIN"
    assert isinstance(AgentRole.ADMIN.value, str)
