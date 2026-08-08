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
from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher
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


def _handler(uow: InMemoryUnitOfWork) -> NotificationHandler:
    # A shared instance, not a fresh one per call: it is what lets the test
    # inspect what got saved through the same repository the handler wrote to.
    return NotificationHandler(uow_factory=lambda: uow)


class TestLeadAssigned:
    def test_notifies_the_agent(self):
        uow = InMemoryUnitOfWork()
        agent_id = uuid.uuid4()
        lead_id = str(uuid.uuid4())

        _handler(uow).handle_lead_assigned(
            LeadAssigned(tenant_id=str(uuid.uuid4()), lead_id=lead_id, agent_id=str(agent_id))
        )

        notifications = uow.notifications.list_by_recipient(agent_id)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.LEAD_ASSIGNED
        assert str(notifications[0].lead_id.value) == lead_id


class TestLeadReassigned:
    def test_notifies_the_new_agent(self):
        uow = InMemoryUnitOfWork()
        new_agent_id = uuid.uuid4()
        lead_id = str(uuid.uuid4())

        _handler(uow).handle_lead_reassigned(
            LeadReassigned(
                tenant_id=str(uuid.uuid4()),
                lead_id=lead_id,
                agent_id=str(new_agent_id),
                previous_agent_id=str(uuid.uuid4()),
            )
        )

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

        _handler(uow).handle_lead_left_unassigned(
            LeadLeftUnassigned(tenant_id=str(tenant_id), lead_id=str(uuid.uuid4()))
        )

        assert len(uow.notifications.list_by_recipient(manager_one.id.value)) == 1
        assert len(uow.notifications.list_by_recipient(manager_two.id.value)) == 1

    def test_skips_an_inactive_manager(self):
        tenant_id = uuid.uuid4()
        agent_repo = InMemoryAgentRepository()
        active = agent_repo.save(_manager(tenant_id))
        inactive = agent_repo.save(_manager(tenant_id, is_active=False))
        uow = InMemoryUnitOfWork(agents=agent_repo)

        _handler(uow).handle_lead_left_unassigned(
            LeadLeftUnassigned(tenant_id=str(tenant_id), lead_id=str(uuid.uuid4()))
        )

        assert len(uow.notifications.list_by_recipient(active.id.value)) == 1
        assert len(uow.notifications.list_by_recipient(inactive.id.value)) == 0

    def test_does_not_raise_without_any_manager(self):
        uow = InMemoryUnitOfWork()

        # The only assertion that matters is that this line does not raise.
        _handler(uow).handle_lead_left_unassigned(
            LeadLeftUnassigned(tenant_id=str(uuid.uuid4()), lead_id=str(uuid.uuid4()))
        )

    def test_an_agent_who_is_not_a_manager_is_not_notified(self):
        tenant_id = uuid.uuid4()
        agent_repo = InMemoryAgentRepository()
        plain_agent = agent_repo.save(_agent(tenant_id))
        uow = InMemoryUnitOfWork(agents=agent_repo)

        _handler(uow).handle_lead_left_unassigned(
            LeadLeftUnassigned(tenant_id=str(tenant_id), lead_id=str(uuid.uuid4()))
        )

        assert len(uow.notifications.list_by_recipient(plain_agent.id.value)) == 0


class TestIntakeRejected:
    def test_notifies_the_manager_with_the_record_id_and_reason(self):
        tenant_id = uuid.uuid4()
        agent_repo = InMemoryAgentRepository()
        manager = agent_repo.save(_manager(tenant_id))
        uow = InMemoryUnitOfWork(agents=agent_repo)
        record_id = str(uuid.uuid4())

        _handler(uow).handle_intake_rejected(
            IntakeRejected(
                tenant_id=str(tenant_id),
                intake_record_id=record_id,
                reason="Formato de correo electrónico inválido",
            )
        )

        notifications = uow.notifications.list_by_recipient(manager.id.value)
        assert len(notifications) == 1
        assert notifications[0].kind == NotificationKind.INTAKE_REJECTED
        assert str(notifications[0].intake_record_id.value) == record_id
        assert "Formato de correo electrónico inválido" in notifications[0].message


class _RaisingNotificationRepository(NotificationRepositoryPort):
    """Stands in for a broken adapter. Only save() is exercised by the
    handler; the rest exist to satisfy the abstract port."""

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
    """The test that justifies the whole design (acceptance criterion 8): the
    notification repository blows up on save, published through the real
    InMemoryEventPublisher — not a Mock — because what is under test is
    precisely whether the publisher absorbs the failure. If this cannot be
    written, publication ended up inside the use case's transaction."""
    tenant_id = uuid.uuid4()
    agent_repo = InMemoryAgentRepository()
    agent_repo.save(_manager(tenant_id))
    uow = InMemoryUnitOfWork(agents=agent_repo, notifications=_RaisingNotificationRepository())

    publisher = InMemoryEventPublisher()
    handler = NotificationHandler(uow_factory=lambda: uow)
    publisher.subscribe(LeadLeftUnassigned, handler.handle_lead_left_unassigned)

    use_case = IngestLeadUseCase(uow=uow, event_publisher=publisher)
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

    # No rules and no available agent means the lead ends up UNASSIGNED,
    # which is what triggers the LeadLeftUnassigned publish below.
    result = use_case.execute(command, existing_record=existing)

    assert result.error is None
    assert result.status == "UNASSIGNED"
    assert existing.status == IntakeRecordStatus.PROMOTED
