import uuid

import pytest

from domain.advisors.advisor import Advisor
from domain.exceptions import DomainException
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.group_id import GroupId
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.advisors.hydrating_advisor_directory import HydratingAdvisorDirectory
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT = uuid.uuid4()


def _advisor(agent_id, tenant=_TENANT, role=AgentRole.AGENT, version=1, name="Ana") -> Advisor:
    return Advisor(AgentId(agent_id), TenantId(tenant), name, role, True, version)


class _Identity:
    def __init__(self, answer=None, error=None) -> None:
        self.answer, self.error, self.calls = answer, error, 0

    def fetch(self, agent_id):
        self.calls += 1
        if self.error:
            raise self.error
        return self.answer


def _directory(identity, uow=None):
    uow = uow or InMemoryUnitOfWork()
    return HydratingAdvisorDirectory(lambda: uow, identity), uow


def _error_code(directory, agent_id) -> str:
    with pytest.raises(DomainException) as exc:
        directory.get(agent_id, _TENANT)
    return exc.value.error_code


def test_a_projected_advisor_is_served_without_asking_identity():
    agent_id, identity = uuid.uuid4(), _Identity()
    directory, uow = _directory(identity)
    uow.advisors.seed(_advisor(agent_id))

    assert directory.get(agent_id, _TENANT).agent_id.value == agent_id
    assert identity.calls == 0


def test_a_missing_advisor_is_hydrated_from_identity_and_stored():
    agent_id = uuid.uuid4()
    directory, uow = _directory(_Identity(answer=_advisor(agent_id, version=4)))

    assert directory.get(agent_id, _TENANT).version == 4
    assert uow.advisors.get(agent_id, _TENANT).version == 4


def test_hydration_keeps_the_group_and_a_newer_stored_state():
    """The re-read is what is returned: identity's answer does not overwrite what is newer."""
    agent_id = uuid.uuid4()
    identity = _Identity(answer=_advisor(agent_id, version=1, name="Stale"))
    directory, uow = _directory(identity)
    group = GroupId(uuid.uuid4())
    uow.advisors.seed(Advisor(AgentId(agent_id), TenantId(_TENANT), "Fresh", AgentRole.AGENT, True, 5, group))

    # Forced through _hydrate: a stored row normally short-circuits before it.
    assert directory._hydrate(agent_id).name == "Fresh"
    assert uow.advisors.get(agent_id, _TENANT).group_id == group


def test_an_agent_identity_does_not_know_is_not_found():
    directory, _ = _directory(_Identity(answer=None))
    assert _error_code(directory, uuid.uuid4()) == "AGENT_NOT_FOUND"


def test_an_agent_of_another_organization_is_not_found_never_forbidden():
    agent_id = uuid.uuid4()
    directory, uow = _directory(_Identity(answer=_advisor(agent_id, tenant=uuid.uuid4())))

    assert _error_code(directory, agent_id) == "AGENT_NOT_FOUND"
    assert uow.advisors.get(agent_id, _TENANT) is None


def test_a_foreign_agent_already_projected_is_not_found_without_asking_identity():
    """Even with identity down: tenant isolation is answered from the projection."""
    agent_id = uuid.uuid4()
    identity = _Identity(error=DomainException("identity is unavailable", error_code="SERVICE_UNAVAILABLE"))
    directory, uow = _directory(identity)
    uow.advisors.seed(_advisor(agent_id, tenant=uuid.uuid4()))

    assert _error_code(directory, agent_id) == "AGENT_NOT_FOUND"
    assert identity.calls == 0


@pytest.mark.parametrize("role", [AgentRole.INTEGRATION, AgentRole.ADMIN])
def test_an_agent_that_is_never_routed_work_is_not_found(role):
    agent_id = uuid.uuid4()
    directory, uow = _directory(_Identity())
    uow.advisors.seed(_advisor(agent_id, role=role))

    assert _error_code(directory, agent_id) == "AGENT_NOT_FOUND"


def test_identity_down_is_service_unavailable_not_a_404():
    error = DomainException("identity is unavailable", error_code="SERVICE_UNAVAILABLE")
    directory, _ = _directory(_Identity(error=error))

    assert _error_code(directory, uuid.uuid4()) == "SERVICE_UNAVAILABLE"
