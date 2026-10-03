from typing import List

from domain.leads.lead import Lead
from domain.rules.scoring_rule import ScoringRule
from domain.value_objects.score_breakdown import AppliedRule, ScoreBreakdown


class ScoringEngine:
    """Accumulates the deltas of the rules a lead satisfies.

    It no longer knows how a comparison works: that moved onto the rule. What
    is left here is ordering, accumulation and the breakdown."""

    def evaluate(self, lead: Lead, rules: List[ScoringRule]) -> ScoreBreakdown:
        applied: List[AppliedRule] = []
        total = 0
        for rule in self._ordered(rules):
            if not rule.matches(lead):
                continue
            applied.append(AppliedRule(rule_id=rule.id, name=rule.name, score_delta=rule.score_delta))
            total += rule.score_delta
            lead.apply_score(rule.score_delta)
        return ScoreBreakdown(applied=applied, total=total)

    @staticmethod
    def _ordered(rules: List[ScoringRule]) -> List[ScoringRule]:
        # The sum is commutative, so priority only shapes the breakdown the
        # manager reads. The id breaks ties so the order is reproducible.
        return sorted(
            (r for r in rules if r.is_active),
            key=lambda r: (-r.priority, str(r.id)),
        )
