import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.enums import AgentMatchMode, AssignmentStrategy, Operator

if TYPE_CHECKING:
    # Only for the type hint in resolve_strategy: importing SalesGroup at
    # module level would create a cycle the moment it needs a rule back.
    from domain.entities.sales_group import SalesGroup


@dataclass
class ScoringRule:
    id: UUID
    name: str
    field: str
    operator: Operator
    value: Any
    score_delta: int

    @classmethod
    def create(
        cls,
        name: str,
        field: str,
        operator: Union[Operator, str],
        value: Any,
        score_delta: int,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "ScoringRule":
        op = Operator(operator) if isinstance(operator, str) else operator
        rid = UUID(str(rule_id)) if rule_id else uuid.uuid4()
        return cls(
            id=rid,
            name=name,
            field=field,
            operator=op,
            value=value,
            score_delta=score_delta,
        )


@dataclass
class AssignmentRule:
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
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "AssignmentRule":
        """Rebuild a stored rule, applying no input validation.

        Deleting a group nulls target_group_id by design, so storage can
        legitimately hold a rule with no target for the manager to resolve.
        create() rejects that state; reading it back must not, or one group
        deletion would break every ingestion for the organization."""
        parsed_agent_ids = [UUID(str(i)) for i in target_agent_ids] if target_agent_ids else []
        parsed_group_id = UUID(str(target_group_id)) if target_group_id else None

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
        )

    def matches_score(self, score: int) -> bool:
        if score < self.min_score:
            return False
        return self.max_score is None or score <= self.max_score

    def resolve_strategy(self, group: Optional["SalesGroup"]) -> AssignmentStrategy:
        """The rule's own strategy, or the group's, or the safe default."""
        if self.strategy is not None:
            return self.strategy
        if group is not None:
            return group.default_strategy
        return AssignmentStrategy.LOWEST_LOAD

    def advance_cursor(self, size: int) -> int:
        """Return the index to use now and move the cursor past it.

        The modulo is applied on read, not on write, so the cursor stays valid
        when agents join or leave the group between two assignments."""
        if size <= 0:
            raise DomainException(
                "No hay candidatos sobre los que rotar",
                error_code="EMPTY_CANDIDATE_POOL",
            )
        index = self.rr_cursor % size
        self.rr_cursor = index + 1
        return index
