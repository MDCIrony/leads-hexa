import uuid
from dataclasses import fields

import pytest

from domain.agents.agent import Agent, normalize_email
from domain.value_objects.agent_id import AgentId
from domain.value_objects.agent_role import AgentRole


def test_agent_entity_creation():
    agent = Agent.create(name="Carlos Lopez", email="clopez@sales.com")
    assert agent.is_active is True
    assert agent.name == "Carlos Lopez"
    assert isinstance(agent.id, AgentId)

    raw_uuid = uuid.uuid4()
    vo_agent_id = AgentId(raw_uuid)
    assert Agent.create("A", "a@test.com", agent_id=str(raw_uuid)).id.value == raw_uuid
    assert Agent.create("B", "b@test.com", agent_id=raw_uuid).id.value == raw_uuid
    assert Agent.create("C", "c@test.com", agent_id=vo_agent_id).id == vo_agent_id


def test_agent_create_defaults_role_to_agent_and_has_no_password_or_tenant():
    agent = Agent.create("A", "a@test.com")
    assert agent.role == AgentRole.AGENT
    assert agent.hashed_password is None
    assert agent.tenant_id is None
    assert agent.version == 1


def test_agent_create_accepts_role_password_tenant_and_version():
    tenant_uuid = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    agent = Agent.create(
        "B", "b@test.com", role="MANAGER", hashed_password="$2b$hash", tenant_id=tenant_uuid, version=7,
    )
    assert agent.role == AgentRole.MANAGER
    assert agent.hashed_password == "$2b$hash"
    assert str(agent.tenant_id) == tenant_uuid
    assert agent.version == 7


def test_the_email_is_stored_normalized():
    assert Agent.create("A", "  Ana@Acme.TEST ").email == "ana@acme.test"
    assert normalize_email(" X@Y.Z ") == "x@y.z"


def test_an_agent_has_no_sales_group():
    # Grouping lives on the leads side; identity must not grow it back.
    assert "group_id" not in {field.name for field in fields(Agent)}


def test_everything_after_the_email_is_keyword_only():
    # The third positional slot used to be group_id: an old call must fail loudly.
    with pytest.raises(TypeError):
        Agent.create("C", "c@test.com", uuid.uuid4())
