import uuid
from typing import List, Optional
from uuid import UUID

from application.dtos.commands import IngestLeadCommand
from application.handlers.notification_handler import NotificationHandler
from application.ports.output.notification_repository_port import NotificationRepositoryPort
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase, payload_of
from domain.entities.agent import Agent
from domain.entities.intake_record import IntakeRecord
from domain.entities.notification import Notification
from domain.events.notification_events import (
    IntakeRejected,
    LeadAssigned,
    LeadLeftUnassigned,
    LeadReassigned,
)
from domain.value_objects.enums import AgentRole, IntakeRecordStatus, NotificationKind
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _manager(tenant_id, is_active: bool = True) -> Agent:
    return Agent.create(
        name=f"Manager {uuid.uuid4()}",
        email=f"{uuid.uuid4()}@test.com",
        role=AgentRole.MANAGER,
        tenant_id=tenant_id,
        is_active=is_active,
    )


def _agent(tenant_id) -> Agent:
    return Agent.create(
        name=f"Agent {uuid.uuid4()}",
        email=f"{uuid.uuid4()}@test.com",
        role=AgentRole.AGENT,
        tenant_id=tenant_id,
    )


def _apply(uow: InMemoryUnitOfWork, event) -> None:
    """Hands the event over the way a consumer receives it: type, tenant and
    the JSON payload, never the object itself."""
    NotificationHandler().apply(event.event_type, event.tenant_id, event.as_payload(), uow)


class TestLeadAssigned:
    def test_notifies_the_agent(self):
        uow = InMemoryUnitOfWork()
        agent_id = uuid.uuid4()
        lead_id = str(uuid.uuid4())

        _apply(uow, LeadAssigned(tenant_id=str(uuid.uuid4()), lead_id=lead_id, agent_id=str(agent_id)))

        notifications = uow.notifications.list_by_recipient(agent_id)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.LEAD_ASSIGNED
        assert notifications[0].message == "Tienes un lead nuevo asignado"
        assert str(notifications[0].lead_id.value) == lead_id


class TestLeadReassigned:
    def test_notifies_the_new_agent(self):
        uow = InMemoryUnitOfWork()
        new_agent_id = uuid.uuid4()
        lead_id = str(uuid.uuid4())

        _apply(uow, LeadReassigned(
            tenant_id=str(uuid.uuid4()),
            lead_id=lead_id,
            agent_id=str(new_agent_id),
            previous_agent_id=str(uuid.uuid4()),
        ))

        notifications = uow.notifications.list_by_recipient(new_agent_id)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.LEAD_REASSIGNED
        assert str(notifications[0].lead_id.value) == lead_id


class TestLeadLeftUnassigned:
    def test_notifies_every_active_manager(self):
        tenant_id = uuid.uuid4()
        agent_repo = InMemoryAgentRepository()
        manager_one = agent_repo.save(_manager(tenant_id))
        manager_two = agent_repo.save(_manager(tenant_id))
        uow = InMemoryUnitOfWork(agents=agent_repo)

        _apply(uow, LeadLeftUnassigned(tenant_id=str(tenant_id), lead_id=str(uuid.uuid4())))

        assert len(uow.notifications.list_by_recipient(manager_one.id.value)) == 1
        assert len(uow.notifications.list_by_recipient(manager_two.id.value)) == 1

    def test_skips_an_inactive_manager(self):
        tenant_id = uuid.uuid4()
        agent_repo = InMemoryAgentRepository()
        active = agent_repo.save(_manager(tenant_id))
        inactive = agent_repo.save(_manager(tenant_id, is_active=False))
        uow = InMemoryUnitOfWork(agents=agent_repo)

        _apply(uow, LeadLeftUnassigned(tenant_id=str(tenant_id), lead_id=str(uuid.uuid4())))

        assert len(uow.notifications.list_by_recipient(active.id.value)) == 1
        assert len(uow.notifications.list_by_recipient(inactive.id.value)) == 0

    def test_does_not_raise_without_any_manager(self):
        uow = InMemoryUnitOfWork()

        # The only assertion that matters is that this line does not raise.
        _apply(uow, LeadLeftUnassigned(tenant_id=str(uuid.uuid4()), lead_id=str(uuid.uuid4())))

    def test_an_agent_who_is_not_a_manager_is_not_notified(self):
        tenant_id = uuid.uuid4()
        agent_repo = InMemoryAgentRepository()
        plain_agent = agent_repo.save(_agent(tenant_id))
        uow = InMemoryUnitOfWork(agents=agent_repo)

        _apply(uow, LeadLeftUnassigned(tenant_id=str(tenant_id), lead_id=str(uuid.uuid4())))

        assert len(uow.notifications.list_by_recipient(plain_agent.id.value)) == 0


class TestIntakeRejected:
    def test_notifies_the_manager_with_the_record_id_and_reason(self):
        tenant_id = uuid.uuid4()
        agent_repo = InMemoryAgentRepository()
        manager = agent_repo.save(_manager(tenant_id))
        uow = InMemoryUnitOfWork(agents=agent_repo)
        record_id = str(uuid.uuid4())

        _apply(uow, IntakeRejected(
            tenant_id=str(tenant_id),
            intake_record_id=record_id,
            reason="Formato de correo electrónico inválido",
        ))

        notifications = uow.notifications.list_by_recipient(manager.id.value)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.INTAKE_REJECTED
        assert str(notifications[0].intake_record_id.value) == record_id
        assert notifications[0].message == (
            "Un registro de entrada no se pudo interpretar: Formato de correo electrónico inválido"
        )


def test_an_unknown_event_type_does_nothing():
    """A topic can carry types this consumer has no rule for; skipping them is
    what keeps one new event from dead-lettering everything behind it."""
    tenant_id = uuid.uuid4()
    agent_repo = InMemoryAgentRepository()
    manager = agent_repo.save(_manager(tenant_id))
    uow = InMemoryUnitOfWork(agents=agent_repo)

    NotificationHandler().apply("LeadArchived", str(tenant_id), {"lead_id": str(uuid.uuid4())}, uow)

    assert uow.notifications.list_by_recipient(manager.id.value) == []


class _RaisingNotificationRepository(NotificationRepositoryPort):
    """Stands in for a broken adapter. Only save() would be exercised; the
    rest exist to satisfy the abstract port."""

    def save(self, notification: Notification) -> Notification:
        raise RuntimeError("notifications table is down")

    def get_by_id_and_recipient(self, notification_id: UUID, recipient_id: UUID) -> Optional[Notification]:
        return None

    def list_by_recipient(
        self, recipient_id: UUID, unread_only: bool = False, limit: int = 100, offset: int = 0
    ) -> List[Notification]:
        return []

    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int:
        return 0

    def mark_all_read(self, recipient_id: UUID) -> int:
        return 0


def test_a_failing_notification_repository_does_not_fail_the_ingestion():
    """Acceptance criterion 8: ingestion only records the notice; turning it
    into notifications is the consumer's job, in its own transaction, so a
    broken notifications table cannot undo a lead."""
    tenant_id = uuid.uuid4()
    agent_repo = InMemoryAgentRepository()
    agent_repo.save(_manager(tenant_id))
    uow = InMemoryUnitOfWork(agents=agent_repo, notifications=_RaisingNotificationRepository())

    command = IngestLeadCommand(
        tenant_id=tenant_id,
        source_id=uuid.uuid4(),
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        company="Acme Corp",
        budget=100.0,
        industry="Tech",
        custom_attributes={},
    )
    existing = uow.intake_records.save(
        IntakeRecord.create(tenant_id=command.tenant_id, source_id=command.source_id, payload=payload_of(command))
    )

    # No rules and no available agent means the lead ends up UNASSIGNED.
    result = IngestLeadUseCase(uow=uow).execute(command, existing_record=existing)

    assert result.error is None
    assert result.status == "UNASSIGNED"
    assert existing.status == IntakeRecordStatus.PROMOTED
    assert [e.event_type for e in uow.outbox.list_unpublished("internal", 10)] == ["LeadLeftUnassigned"]
