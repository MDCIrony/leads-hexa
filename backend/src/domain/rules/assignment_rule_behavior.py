from typing import TYPE_CHECKING, List, Optional

from domain.exceptions import DomainException
from domain.value_objects.criterion import Criterion, all_match
from domain.value_objects.enums import AssignmentStrategy

if TYPE_CHECKING:
    # Only for the type hint in resolve_strategy: importing SalesGroup at
    # module level would create a cycle the moment it needs a rule back.
    from domain.groups.sales_group import SalesGroup
    from domain.leads.lead import Lead


class AssignmentRuleBehavior:
    """Matching and rotation of AssignmentRule, split off to keep each file small.

    Not meant to be used alone: it reads the fields AssignmentRule declares."""

    min_score: int
    max_score: Optional[int]
    strategy: Optional[AssignmentStrategy]
    conditions: List[Criterion]
    rr_cursor: int

    def matches_score(self, score: int) -> bool:
        if score < self.min_score:
            return False
        return self.max_score is None or score <= self.max_score

    def matches(self, lead: "Lead") -> bool:
        """Band and conditions, both required.

        An empty condition list means the rule discriminates by score alone,
        which is what every rule written before this phase does."""
        return self.matches_score(int(lead.score)) and all_match(self.conditions, lead)

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
