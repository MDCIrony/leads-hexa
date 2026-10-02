from enum import Enum


class AgentRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    AGENT = "AGENT"
    # A machine principal, never a person: excluded from POST /agents' role
    # choices and from POST /auth/login (ADR-0028). Its only door in is
    # POST /agents/integration-credential.
    INTEGRATION = "INTEGRATION"
