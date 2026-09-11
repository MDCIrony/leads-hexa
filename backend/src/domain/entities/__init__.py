from domain.entities.lead import Lead
from domain.entities.rule import AssignmentRule, ScoringRule
from domain.entities.agent import Agent
from domain.entities.sales_group import SalesGroup
from domain.entities.webhook import WebhookConfig
from domain.entities.social_identity import SocialIdentity

__all__ = [
    "Lead",
    "ScoringRule",
    "AssignmentRule",
    "SalesGroup",
    "Agent",
    "WebhookConfig",
    "SocialIdentity",
]
