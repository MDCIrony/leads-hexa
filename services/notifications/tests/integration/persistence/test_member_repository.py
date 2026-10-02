from uuid import uuid4

from domain.members.member import Member


def _member(tenant_id, role="MANAGER", is_active=True, version=1) -> Member:
    return Member(agent_id=uuid4(), tenant_id=tenant_id, role=role, is_active=is_active, version=version)


def test_saves_and_reads_back_a_member(uow_factory):
    member = _member(uuid4(), version=4)
    with uow_factory() as uow:
        uow.members.save(member)

        assert uow.members.get(member.agent_id) == member
        assert uow.members.get(uuid4()) is None


def test_saving_again_replaces_the_row(uow_factory):
    member = _member(uuid4(), version=1)
    with uow_factory() as uow:
        uow.members.save(member)
        newer = Member(member.agent_id, member.tenant_id, "AGENT", False, 2)
        uow.members.save(newer)

        assert uow.members.get(member.agent_id) == newer


def test_active_manager_ids_returns_only_active_managers_of_the_tenant(uow_factory):
    """The SQL repeats Member.receives_organization_notices; this keeps the two in step."""
    tenant_id = uuid4()
    members = [
        _member(tenant_id),
        _member(tenant_id, is_active=False),
        _member(tenant_id, role="AGENT"),
        _member(uuid4()),
    ]
    with uow_factory() as uow:
        for member in members:
            uow.members.save(member)

        found = uow.members.active_manager_ids(tenant_id)

    assert found == [members[0].agent_id]
    assert [m.receives_organization_notices for m in members[:3]] == [True, False, False]
