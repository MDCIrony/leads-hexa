from uuid import UUID

from application.ports.input.members import ProjectMemberInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.members.member import Member


class ProjectMemberUseCase(ProjectMemberInputPort):
    """Keeps the local member projection current from the identity service's agent events."""

    def apply(self, tenant_id: str | None, payload: dict, uow: UnitOfWorkPort) -> bool:
        if tenant_id is None:
            # The platform administrator has no organization and receives no organization notices.
            return False
        member = Member(
            agent_id=UUID(payload["agent_id"]),
            tenant_id=UUID(tenant_id),
            role=payload["role"],
            is_active=payload["is_active"],
            version=payload["version"],
        )
        if not member.supersedes(uow.members.get(member.agent_id)):
            return False
        uow.members.save(member)
        return True
