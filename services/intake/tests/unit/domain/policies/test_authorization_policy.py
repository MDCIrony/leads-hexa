from types import SimpleNamespace

import pytest

from domain.exceptions import ForbiddenException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.agent_role import AgentRole


def _actor(role: AgentRole):
    return SimpleNamespace(role=role)


def test_a_manager_manages_its_organization():
    assert AuthorizationPolicy.can_manage_organization(_actor(AgentRole.MANAGER)) is True
    AuthorizationPolicy.ensure_can_manage_organization(_actor(AgentRole.MANAGER))


@pytest.mark.parametrize("role", [AgentRole.ADMIN, AgentRole.AGENT, AgentRole.INTEGRATION])
def test_nobody_else_manages_an_organization(role):
    # The platform administrator is a different plane, not a super-manager.
    assert AuthorizationPolicy.can_manage_organization(_actor(role)) is False
    with pytest.raises(ForbiddenException):
        AuthorizationPolicy.ensure_can_manage_organization(_actor(role))
