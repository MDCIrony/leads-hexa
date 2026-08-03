import uuid
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union
from uuid import UUID

from domain.value_objects.enums import AssignmentStrategy, Operator


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
class RoutingRule:
    id: UUID
    min_score: int
    target_team: str
    assignment_strategy: AssignmentStrategy
    target_agent_ids: List[UUID] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        min_score: int,
        target_team: str,
        assignment_strategy: Union[AssignmentStrategy, str],
        target_agent_ids: Optional[List[Union[str, UUID]]] = None,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "RoutingRule":
        strat = (
            AssignmentStrategy(assignment_strategy)
            if isinstance(assignment_strategy, str)
            else assignment_strategy
        )
        rid = UUID(str(rule_id)) if rule_id else uuid.uuid4()
        parsed_target_ids = (
            [UUID(str(i)) for i in target_agent_ids] if target_agent_ids else []
        )
        return cls(
            id=rid,
            min_score=min_score,
            target_team=target_team,
            assignment_strategy=strat,
            target_agent_ids=parsed_target_ids,
        )
