import uuid

from domain.members.member import Member


def _member(role: str = "MANAGER", is_active: bool = True, version: int = 1) -> Member:
    return Member(agent_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role=role, is_active=is_active, version=version)


class TestReceivesOrganizationNotices:
    def test_an_active_manager_receives_them(self):
        assert _member().receives_organization_notices is True

    def test_an_inactive_manager_does_not(self):
        assert _member(is_active=False).receives_organization_notices is False

    def test_an_agent_does_not(self):
        assert _member(role="AGENT").receives_organization_notices is False


class TestSupersedes:
    def test_anything_supersedes_nothing(self):
        assert _member().supersedes(None) is True

    def test_a_newer_version_supersedes(self):
        assert _member(version=3).supersedes(_member(version=2)) is True

    def test_the_same_version_does_not(self):
        assert _member(version=2).supersedes(_member(version=2)) is False

    def test_an_older_version_does_not(self):
        assert _member(version=1).supersedes(_member(version=2)) is False
