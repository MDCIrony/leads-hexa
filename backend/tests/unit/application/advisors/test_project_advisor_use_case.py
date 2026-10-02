import uuid

from application.use_cases.advisors.project_advisor import ProjectAdvisorUseCase
from domain.value_objects.enums import AgentRole
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT = str(uuid.uuid4())


def _payload(agent_id: str, version: int, name: str = "Ana", is_active: bool = True) -> dict:
    return {"agent_id": agent_id, "tenant_id": _TENANT, "name": name, "role": "AGENT",
            "is_active": is_active, "version": version}


def test_a_new_agent_becomes_an_advisor_without_a_group():
    uow, agent_id = InMemoryUnitOfWork(), str(uuid.uuid4())

    assert ProjectAdvisorUseCase().apply(_TENANT, _payload(agent_id, 1), uow) is True

    advisor = uow.advisors.get(uuid.UUID(agent_id), uuid.UUID(_TENANT))
    assert (advisor.name, advisor.role, advisor.is_active, advisor.version, advisor.group_id) == (
        "Ana", AgentRole.AGENT, True, 1, None)


def test_an_older_state_changes_nothing():
    uow, agent_id = InMemoryUnitOfWork(), str(uuid.uuid4())
    ProjectAdvisorUseCase().apply(_TENANT, _payload(agent_id, 3, name="Ana B."), uow)

    assert ProjectAdvisorUseCase().apply(_TENANT, _payload(agent_id, 2, is_active=False), uow) is False

    advisor = uow.advisors.get(uuid.UUID(agent_id), uuid.UUID(_TENANT))
    assert (advisor.name, advisor.is_active, advisor.version) == ("Ana B.", True, 3)


def test_a_newer_state_keeps_the_group_lead_core_assigned():
    uow, agent_id = InMemoryUnitOfWork(), str(uuid.uuid4())
    group_id = uuid.uuid4()
    ProjectAdvisorUseCase().apply(_TENANT, _payload(agent_id, 1), uow)
    uow.advisors.set_group(uuid.UUID(agent_id), uuid.UUID(_TENANT), group_id)

    assert ProjectAdvisorUseCase().apply(_TENANT, _payload(agent_id, 2, is_active=False), uow) is True

    advisor = uow.advisors.get(uuid.UUID(agent_id), uuid.UUID(_TENANT))
    assert (advisor.is_active, advisor.group_id.value) == (False, group_id)


def test_the_platform_admin_is_not_projected():
    uow, agent_id = InMemoryUnitOfWork(), str(uuid.uuid4())

    assert ProjectAdvisorUseCase().apply(None, {**_payload(agent_id, 1), "tenant_id": None}, uow) is False

    assert uow.advisors.advisors == {}
