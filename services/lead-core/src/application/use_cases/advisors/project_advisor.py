from typing import Optional

from application.ports.input.advisors.project_advisor_port import ProjectAdvisorInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.advisors.advisor import Advisor
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole
from domain.value_objects.tenant_id import TenantId


class ProjectAdvisorUseCase(ProjectAdvisorInputPort):
    """Keeps the advisors projection current from identity's agent state events."""

    def apply(self, tenant_id: Optional[str], payload: dict, uow: UnitOfWorkPort) -> bool:
        if tenant_id is None:
            # The platform administrator has no organization to route leads in.
            return False
        advisor = Advisor(
            agent_id=AgentId(payload["agent_id"]),
            tenant_id=TenantId(tenant_id),
            name=payload["name"],
            role=AgentRole(payload["role"]),
            is_active=payload["is_active"],
            version=payload["version"],
        )
        # Only the fast path: upsert_identity repeats the check in SQL, where
        # two concurrent writers cannot both pass it.
        if not advisor.supersedes(uow.advisors.get(advisor.agent_id.value, advisor.tenant_id.value)):
            return False
        uow.advisors.upsert_identity(advisor)
        return True
