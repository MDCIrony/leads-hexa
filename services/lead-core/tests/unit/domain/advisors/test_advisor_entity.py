import pytest

from domain.advisors.advisor import Advisor
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.tenant_id import TenantId


def _advisor(version: int = 1, role: AgentRole = AgentRole.AGENT, is_active: bool = True) -> Advisor:
    return Advisor(AgentId(), TenantId(), "Ana", role, is_active, version)


def test_a_first_state_supersedes_nothing_stored():
    assert _advisor().supersedes(None)


@pytest.mark.parametrize("stored, incoming, expected", [(1, 2, True), (2, 2, False), (3, 2, False)])
def test_only_a_strictly_newer_version_supersedes(stored, incoming, expected):
    assert _advisor(incoming).supersedes(_advisor(stored)) is expected


@pytest.mark.parametrize("role", [AgentRole.AGENT, AgentRole.MANAGER])
def test_an_active_person_of_the_organization_is_assignable(role):
    assert _advisor(role=role).is_assignable


@pytest.mark.parametrize("role", [AgentRole.INTEGRATION, AgentRole.ADMIN])
def test_machine_credentials_and_the_platform_admin_are_never_assignable(role):
    assert not _advisor(role=role).is_assignable


def test_an_inactive_advisor_is_not_assignable():
    assert not _advisor(is_active=False).is_assignable


@pytest.mark.parametrize("role, expected", [(AgentRole.AGENT, True), (AgentRole.MANAGER, True),
                                            (AgentRole.INTEGRATION, False), (AgentRole.ADMIN, False)])
def test_routability_depends_on_the_role_alone(role, expected):
    assert _advisor(role=role, is_active=False).is_routable is expected


def test_the_engine_reads_the_agent_id_as_id():
    advisor = _advisor()
    assert advisor.id == advisor.agent_id
