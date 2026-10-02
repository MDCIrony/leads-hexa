import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.rules.assignment_rule_behavior import AssignmentRuleBehavior
from domain.value_objects.criterion import Criterion
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy


@dataclass
class AssignmentRule(AssignmentRuleBehavior):
    """Decides which agents may receive a lead of a given score.

    Replaces the free-form routing rule that came before it. The
    differences are what made that one unusable: no name to show in an
    interface, no upper bound so bands could not be expressed, no priority
    so ties resolved by whatever order the database returned rows, and a
    rotation cursor living in memory."""

    id: UUID
    tenant_id: UUID
    name: str
    min_score: int = 0
    max_score: Optional[int] = None
    target_group_id: Optional[UUID] = None
    target_agent_ids: List[UUID] = field(default_factory=list)
    agent_match_mode: AgentMatchMode = AgentMatchMode.ANY
    strategy: Optional[AssignmentStrategy] = None
    priority: int = 0
    is_active: bool = True
    rr_cursor: int = 0
    # Empty by default so every rule written before this phase keeps
    # discriminating by band alone, with no data migration required.
    conditions: List[Criterion] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        min_score: int = 0,
        max_score: Optional[int] = None,
        target_group_id: Optional[Union[str, UUID]] = None,
        target_agent_ids: Optional[List[Union[str, UUID]]] = None,
        agent_match_mode: Union[str, AgentMatchMode] = AgentMatchMode.ANY,
        strategy: Optional[Union[str, AssignmentStrategy]] = None,
        priority: int = 0,
        is_active: bool = True,
        rr_cursor: int = 0,
        conditions: Optional[List[Union[Criterion, Dict[str, Any]]]] = None,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "AssignmentRule":
        clean_name = (name or "").strip()
        if not clean_name:
            raise DomainException(
                "El nombre de la regla no puede estar vacío",
                error_code="INVALID_RULE_NAME",
            )
        if max_score is not None and max_score < min_score:
            raise DomainException(
                "La puntuación máxima no puede ser menor que la mínima",
                error_code="INVALID_SCORE_BAND",
            )

        if not target_group_id and not target_agent_ids:
            raise DomainException(
                "La regla debe apuntar a un grupo o a asesores concretos",
                error_code="RULE_WITHOUT_TARGET",
            )

        return cls.restore(
            tenant_id=tenant_id,
            name=clean_name,
            min_score=min_score,
            max_score=max_score,
            target_group_id=target_group_id,
            target_agent_ids=target_agent_ids,
            agent_match_mode=agent_match_mode,
            strategy=strategy,
            priority=priority,
            is_active=is_active,
            rr_cursor=rr_cursor,
            conditions=conditions,
            rule_id=rule_id,
        )

    @classmethod
    def restore(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        min_score: int = 0,
        max_score: Optional[int] = None,
        target_group_id: Optional[Union[str, UUID]] = None,
        target_agent_ids: Optional[List[Union[str, UUID]]] = None,
        agent_match_mode: Union[str, AgentMatchMode] = AgentMatchMode.ANY,
        strategy: Optional[Union[str, AssignmentStrategy]] = None,
        priority: int = 0,
        is_active: bool = True,
        rr_cursor: int = 0,
        conditions: Optional[List[Union[Criterion, Dict[str, Any]]]] = None,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "AssignmentRule":
        """Rebuild a stored rule, applying no input validation.

        Deleting a group nulls target_group_id by design, so storage can
        legitimately hold a rule with no target for the manager to resolve.
        create() rejects that state; reading it back must not, or one group
        deletion would break every ingestion for the organization."""
        parsed_agent_ids = [UUID(str(i)) for i in target_agent_ids] if target_agent_ids else []
        parsed_group_id = UUID(str(target_group_id)) if target_group_id else None
        parsed_conditions = [
            c if isinstance(c, Criterion) else Criterion.from_dict(c) for c in conditions or []
        ]

        mode = (
            agent_match_mode
            if isinstance(agent_match_mode, AgentMatchMode)
            else AgentMatchMode(agent_match_mode)
        )
        parsed_strategy: Optional[AssignmentStrategy]
        if strategy is None:
            parsed_strategy = None
        elif isinstance(strategy, AssignmentStrategy):
            parsed_strategy = strategy
        else:
            parsed_strategy = AssignmentStrategy(strategy)

        return cls(
            id=UUID(str(rule_id)) if rule_id else uuid.uuid4(),
            tenant_id=UUID(str(tenant_id)),
            name=(name or "").strip(),
            min_score=min_score,
            max_score=max_score,
            target_group_id=parsed_group_id,
            target_agent_ids=parsed_agent_ids,
            agent_match_mode=mode,
            strategy=parsed_strategy,
            priority=priority,
            is_active=is_active,
            rr_cursor=rr_cursor,
            conditions=parsed_conditions,
        )
