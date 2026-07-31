from typing import Any, List
from domain.entities.lead import Lead
from domain.entities.rule import ScoringRule
from domain.value_objects.enums import Operator

class ScoringEngine:
    @staticmethod
    def _get_field_value(lead: Lead, field_name: str) -> Any:
        if field_name.startswith("custom_attributes."):
            key = field_name.split(".", 1)[1]
            return lead.custom_attributes.get(key)
        
        if hasattr(lead, field_name):
            val = getattr(lead, field_name)
            if hasattr(val, "value"):
                return val.value
            if hasattr(val, "amount"):
                return val.amount
            return val
        
        return lead.custom_attributes.get(field_name)

    @staticmethod
    def evaluate_rule(lead: Lead, rule: ScoringRule) -> bool:
        lead_val = ScoringEngine._get_field_value(lead, rule.field)
        rule_val = rule.value
        op = rule.operator

        if lead_val is None:
            return False

        if op == Operator.EQUALS:
            return str(lead_val) == str(rule_val) if isinstance(rule_val, str) else lead_val == rule_val
        elif op == Operator.NOT_EQUALS:
            return lead_val != rule_val
        elif op == Operator.GREATER_THAN:
            try:
                return float(lead_val) > float(rule_val)
            except (ValueError, TypeError):
                return False
        elif op == Operator.LESS_THAN:
            try:
                return float(lead_val) < float(rule_val)
            except (ValueError, TypeError):
                return False
        elif op == Operator.CONTAINS:
            if isinstance(lead_val, (str, list, dict)):
                return str(rule_val) in lead_val if isinstance(lead_val, str) else rule_val in lead_val
            return False
        elif op == Operator.IN:
            if isinstance(rule_val, (list, tuple, set)):
                return lead_val in rule_val
            return False
        
        return False

    def evaluate(self, lead: Lead, rules: List[ScoringRule]) -> int:
        total_delta = 0
        for rule in rules:
            if self.evaluate_rule(lead, rule):
                total_delta += rule.score_delta
                lead.apply_score(rule.score_delta)
        return total_delta
