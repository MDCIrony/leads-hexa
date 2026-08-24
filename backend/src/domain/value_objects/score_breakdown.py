from dataclasses import dataclass, field
from typing import Any, Dict, List
from uuid import UUID


@dataclass(frozen=True)
class AppliedRule:
    """One rule that actually fired, kept so the interface can explain a score."""

    rule_id: UUID
    name: str
    score_delta: int

    def as_dict(self) -> Dict[str, Any]:
        """One shape wherever this rule leaves the process — the row it is
        stored in and the event it is published in must not drift apart."""
        return {"rule_id": str(self.rule_id), "name": self.name, "score_delta": self.score_delta}


@dataclass(frozen=True)
class ScoreBreakdown:
    applied: List[AppliedRule] = field(default_factory=list)
    total: int = 0
