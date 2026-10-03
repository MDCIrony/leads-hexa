import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID

from domain.value_objects.criterion import Criterion, all_match

if TYPE_CHECKING:
    from domain.leads.lead import Lead


@dataclass
class ScoringRule:
    """A rule that adds or subtracts points when all its conditions hold.

    Several conditions instead of one is what lets a manager write "high
    budget AND target industry" as a single rule. Alternatives are separate
    rules: there is no OR."""

    id: UUID
    tenant_id: UUID
    name: str
    conditions: List[Criterion]
    score_delta: int
    priority: int = 0
    is_active: bool = True

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID],
        name: str,
        conditions: List[Union[Criterion, Dict[str, Any]]],
        score_delta: int,
        priority: int = 0,
        is_active: bool = True,
        rule_id: Optional[Union[str, UUID]] = None,
    ) -> "ScoringRule":
        # Accepts dicts so the SQL adapter can hand over what JSONB gave it
        # without importing Criterion to rebuild each one.
        parsed = [c if isinstance(c, Criterion) else Criterion.from_dict(c) for c in conditions]
        return cls(
            id=UUID(str(rule_id)) if rule_id else uuid.uuid4(),
            tenant_id=UUID(str(tenant_id)),
            name=name,
            conditions=parsed,
            score_delta=score_delta,
            priority=priority,
            is_active=is_active,
        )

    def matches(self, lead: "Lead") -> bool:
        return all_match(self.conditions, lead)
