import uuid
from types import SimpleNamespace

import pytest

from domain.exceptions import ForbiddenException
from domain.policies.authorization_policy import AuthorizationPolicy


def test_an_actor_with_an_organization_passes():
    AuthorizationPolicy.ensure_is_organization_member(SimpleNamespace(tenant_id=uuid.uuid4()))


def test_an_actor_without_an_organization_is_forbidden():
    # The platform administrator operates on a different plane and has no organization.
    with pytest.raises(ForbiddenException) as exc:
        AuthorizationPolicy.ensure_is_organization_member(SimpleNamespace(tenant_id=None))
    assert exc.value.error_code == "FORBIDDEN"
