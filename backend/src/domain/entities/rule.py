import uuid
from dataclasses import dataclass, field
from typing import Any, List
from domain.value_objects.enums import Operator, AssignmentStrategy

@dataclass
class ScoringRule:
    id: uuid.UUID
    name: str
    field: str
    operator: Operator
    value: Any
    score_delta: int

@dataclass
class RoutingRule:
    id: uuid.UUID
    min_score: int
    target_team: str
    assignment_strategy: AssignmentStrategy
    target_agent_ids: List[uuid.UUID] = field(default_factory=list)
