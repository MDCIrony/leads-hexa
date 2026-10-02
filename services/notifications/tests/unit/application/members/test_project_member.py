import uuid

from application.use_cases.members.project_member import ProjectMemberUseCase
from domain.members.member import Member
from tests.unit.application.fakes import InMemoryUnitOfWork


def _payload(agent_id, role: str = "MANAGER", is_active: bool = True, version: int = 1) -> dict:
    return {"agent_id": str(agent_id), "role": role, "is_active": is_active, "version": version}


def _apply(uow: InMemoryUnitOfWork, tenant_id, payload: dict) -> bool:
    return ProjectMemberUseCase().apply(None if tenant_id is None else str(tenant_id), payload, uow)


def test_a_first_sighting_is_stored():
    uow, tenant_id, agent_id = InMemoryUnitOfWork(), uuid.uuid4(), uuid.uuid4()

    assert _apply(uow, tenant_id, _payload(agent_id)) is True

    assert uow.members.get(agent_id) == Member(
        agent_id=agent_id, tenant_id=tenant_id, role="MANAGER", is_active=True, version=1
    )


def test_a_newer_version_replaces_the_stored_one():
    uow, tenant_id, agent_id = InMemoryUnitOfWork(), uuid.uuid4(), uuid.uuid4()
    _apply(uow, tenant_id, _payload(agent_id, version=1))

    assert _apply(uow, tenant_id, _payload(agent_id, is_active=False, version=2)) is True

    assert uow.members.get(agent_id).is_active is False
    assert uow.members.get(agent_id).version == 2


def test_the_same_version_is_ignored():
    uow, tenant_id, agent_id = InMemoryUnitOfWork(), uuid.uuid4(), uuid.uuid4()
    _apply(uow, tenant_id, _payload(agent_id, version=2))

    assert _apply(uow, tenant_id, _payload(agent_id, role="AGENT", version=2)) is False

    assert uow.members.get(agent_id).role == "MANAGER"


def test_an_older_version_is_ignored():
    # Redelivery and rebalances reorder events; the stale one must not undo a deactivation.
    uow, tenant_id, agent_id = InMemoryUnitOfWork(), uuid.uuid4(), uuid.uuid4()
    _apply(uow, tenant_id, _payload(agent_id, is_active=False, version=3))

    assert _apply(uow, tenant_id, _payload(agent_id, is_active=True, version=2)) is False

    assert uow.members.get(agent_id).is_active is False


def test_an_agent_without_organization_is_not_stored():
    # The platform administrator receives no organization notices.
    uow, agent_id = InMemoryUnitOfWork(), uuid.uuid4()

    assert _apply(uow, None, _payload(agent_id, role="ADMIN")) is False

    assert uow.members.get(agent_id) is None
