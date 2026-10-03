from typing import List, Optional

from domain.rules.disqualification_rule import DisqualificationRule
from domain.leads.lead import Lead


class ViabilityEngine:
    """Answers whether a lead can be worked at all, before it is scored."""

    def evaluate(self, lead: Lead, rules: List[DisqualificationRule]) -> Optional[DisqualificationRule]:
        """Returns the first rule that disqualifies the lead, or None.

        The first one wins rather than all of them: the lead records one
        reason, and priority is what the manager uses to decide which."""
        for rule in self._ordered(rules):
            if rule.matches(lead):
                return rule
        return None

    @staticmethod
    def _ordered(rules: List[DisqualificationRule]) -> List[DisqualificationRule]:
        return sorted(
            (r for r in rules if r.is_active),
            key=lambda r: (-r.priority, str(r.id)),
        )
