from enum import Enum

class Operator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    CONTAINS = "CONTAINS"
    IN = "IN"

class LeadStatus(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    DISCARDED = "DISCARDED"
    # Retired in F2b, when IntakeRecord captures what fails validation and a
    # Lead stops being the place where a rejected payload lands.
    FAILED = "FAILED"

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

class AgentMatchMode(str, Enum):
    """How a rule combines its target group with its named agents.

    ANY is the default because the alternative silently drops a named agent
    that happens to belong to a different group — the caller asked for that
    person explicitly, so excluding them is never what they meant."""

    ANY = "ANY"
    ONLY = "ONLY"
