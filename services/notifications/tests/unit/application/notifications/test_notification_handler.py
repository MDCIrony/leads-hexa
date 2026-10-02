import uuid

from application.use_cases.notifications.notification_handler import NotificationHandler
from domain.members.member import Member
from domain.notifications.kind import NotificationKind
from tests.unit.application.fakes import InMemoryUnitOfWork


def _member(tenant_id, role: str = "MANAGER", is_active: bool = True) -> Member:
    return Member(agent_id=uuid.uuid4(), tenant_id=tenant_id, role=role, is_active=is_active, version=1)


def _seed(uow: InMemoryUnitOfWork, member: Member) -> Member:
    uow.members.save(member)
    return member


def _apply(uow: InMemoryUnitOfWork, event_type: str, tenant_id, payload: dict) -> None:
    """Hands the event over the way a consumer receives it: type, tenant and the JSON payload."""
    NotificationHandler().apply(event_type, str(tenant_id), payload, uow)


class TestLeadAssigned:
    def test_notifies_the_agent(self):
        uow = InMemoryUnitOfWork()
        agent_id, lead_id = uuid.uuid4(), str(uuid.uuid4())

        _apply(uow, "LeadAssigned", uuid.uuid4(), {"lead_id": lead_id, "agent_id": str(agent_id)})

        notifications = uow.notifications.list_by_recipient(agent_id)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.LEAD_ASSIGNED
        assert notifications[0].message == "Tienes un lead nuevo asignado"
        assert str(notifications[0].lead_id) == lead_id


class TestLeadReassigned:
    def test_notifies_the_new_agent(self):
        uow = InMemoryUnitOfWork()
        new_agent_id, lead_id = uuid.uuid4(), str(uuid.uuid4())

        _apply(uow, "LeadReassigned", uuid.uuid4(), {
            "lead_id": lead_id, "agent_id": str(new_agent_id), "previous_agent_id": str(uuid.uuid4()),
        })

        notifications = uow.notifications.list_by_recipient(new_agent_id)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.LEAD_REASSIGNED
        assert notifications[0].message == "Te han reasignado un lead"
        assert str(notifications[0].lead_id) == lead_id


class TestLeadLeftUnassigned:
    def test_notifies_every_active_manager(self):
        tenant_id, uow = uuid.uuid4(), InMemoryUnitOfWork()
        one, two = _seed(uow, _member(tenant_id)), _seed(uow, _member(tenant_id))

        _apply(uow, "LeadLeftUnassigned", tenant_id, {"lead_id": str(uuid.uuid4())})

        assert len(uow.notifications.list_by_recipient(one.agent_id)) == 1
        assert len(uow.notifications.list_by_recipient(two.agent_id)) == 1
        message = uow.notifications.list_by_recipient(one.agent_id)[0].message
        assert message == "Un lead no encontró asesor y espera asignación manual"

    def test_skips_an_inactive_manager(self):
        tenant_id, uow = uuid.uuid4(), InMemoryUnitOfWork()
        active = _seed(uow, _member(tenant_id))
        inactive = _seed(uow, _member(tenant_id, is_active=False))

        _apply(uow, "LeadLeftUnassigned", tenant_id, {"lead_id": str(uuid.uuid4())})

        assert len(uow.notifications.list_by_recipient(active.agent_id)) == 1
        assert uow.notifications.list_by_recipient(inactive.agent_id) == []

    def test_skips_a_manager_of_another_organization(self):
        uow = InMemoryUnitOfWork()
        stranger = _seed(uow, _member(uuid.uuid4()))

        _apply(uow, "LeadLeftUnassigned", uuid.uuid4(), {"lead_id": str(uuid.uuid4())})

        assert uow.notifications.list_by_recipient(stranger.agent_id) == []

    def test_does_not_raise_without_any_manager(self):
        # The only assertion that matters is that this line does not raise.
        _apply(InMemoryUnitOfWork(), "LeadLeftUnassigned", uuid.uuid4(), {"lead_id": str(uuid.uuid4())})

    def test_an_agent_who_is_not_a_manager_is_not_notified(self):
        tenant_id, uow = uuid.uuid4(), InMemoryUnitOfWork()
        plain = _seed(uow, _member(tenant_id, role="AGENT"))

        _apply(uow, "LeadLeftUnassigned", tenant_id, {"lead_id": str(uuid.uuid4())})

        assert uow.notifications.list_by_recipient(plain.agent_id) == []


class TestIntakeRejected:
    def test_notifies_the_manager_with_the_record_id_and_reason(self):
        tenant_id, uow = uuid.uuid4(), InMemoryUnitOfWork()
        manager = _seed(uow, _member(tenant_id))
        record_id = str(uuid.uuid4())

        _apply(uow, "IntakeRejected", tenant_id, {
            "intake_record_id": record_id, "reason": "Formato de correo electrónico inválido",
        })

        notifications = uow.notifications.list_by_recipient(manager.agent_id)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.INTAKE_REJECTED
        assert str(notifications[0].intake_record_id) == record_id
        assert notifications[0].message == (
            "Un registro de entrada no se pudo interpretar: Formato de correo electrónico inválido"
        )


def test_an_unknown_event_type_does_nothing():
    """A topic can carry types this consumer has no rule for; skipping them is
    what keeps one new event from dead-lettering everything behind it."""
    tenant_id, uow = uuid.uuid4(), InMemoryUnitOfWork()
    manager = _seed(uow, _member(tenant_id))

    _apply(uow, "LeadArchived", tenant_id, {"lead_id": str(uuid.uuid4())})

    assert uow.notifications.list_by_recipient(manager.agent_id) == []
