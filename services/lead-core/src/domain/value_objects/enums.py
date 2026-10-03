from enum import Enum

class Operator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    CONTAINS = "CONTAINS"
    IN = "IN"
    # Emptiness is a question about presence, not about value, and it is the
    # only way to express "has no way of being contacted".
    IS_EMPTY = "IS_EMPTY"
    IS_NOT_EMPTY = "IS_NOT_EMPTY"

class LeadStatus(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    DISCARDED = "DISCARDED"

class AssignmentStrategy(str, Enum):
    ROUND_ROBIN = "ROUND_ROBIN"
    LOWEST_LOAD = "LOWEST_LOAD"
    DIRECT_AGENT = "DIRECT_AGENT"

class WebhookEventType(str, Enum):
    LEAD_INGESTED = "LEAD_INGESTED"
    LEAD_QUALIFIED = "LEAD_QUALIFIED"
    LEAD_ASSIGNED = "LEAD_ASSIGNED"
    LEAD_PROCESSED = "LEAD_PROCESSED"
    PROCESSING_ERROR = "PROCESSING_ERROR"

class AgentRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    AGENT = "AGENT"
    # A machine principal, never a person (ADR-0028): never assignable, and
    # it reaches only the integration route.
    INTEGRATION = "INTEGRATION"

class AgentMatchMode(str, Enum):
    """How a rule combines its target group with its named agents.

    ANY is the default because the alternative silently drops a named agent
    that happens to belong to a different group — the caller asked for that
    person explicitly, so excluding them is never what they meant."""

    ANY = "ANY"
    ONLY = "ONLY"
