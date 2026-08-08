from dataclasses import dataclass, field
from typing import List
from uuid import UUID


@dataclass(frozen=True)
class AppliedRule:
    """One rule that actually fired, kept so the interface can explain a score."""

    rule_id: UUID
    name: str
    score_delta: int


@dataclass(frozen=True)
class ScoreBreakdown:
    applied: List[AppliedRule] = field(default_factory=list)
    total: int = 0
