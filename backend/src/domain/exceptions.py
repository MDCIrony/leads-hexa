class DomainException(Exception):
    """Base domain exception."""
    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

class InvalidEmailException(DomainException):
    """Raised when an email format fails domain validation."""
    def __init__(self, message: str = "Formato de correo electrónico inválido"):
        super().__init__(message, error_code="INVALID_EMAIL")

class InvalidBudgetException(DomainException):
    """Raised when a budget/amount value is invalid (< 0)."""
    def __init__(self, message: str = "Presupuesto inválido"):
        super().__init__(message, error_code="INVALID_BUDGET")

class InvalidUUIDException(DomainException):
    """Raised when a UUID v4 format is invalid."""
    def __init__(self, message: str = "Formato de UUID inválido"):
        super().__init__(message, error_code="INVALID_UUID")

class InvalidRuleException(DomainException):
    """Raised when a scoring/routing rule or its operator is invalid."""
    def __init__(self, message: str = "Regla de scoring o routing inválida"):
        super().__init__(message, error_code="INVALID_RULE")

class LeadRoutingException(DomainException):
    """Raised when lead assignment/routing fails."""
    def __init__(self, message: str = "Fallo en el enrutamiento del lead"):
        super().__init__(message, error_code="ROUTING_FAILED")

class AgentNotFoundException(DomainException):
    """Raised when a requested agent id does not exist."""
    def __init__(self, message: str = "Agent not found"):
        super().__init__(message, error_code="AGENT_NOT_FOUND", status_code=404)

class InvalidCredentialsException(DomainException):
    """Raised when a login attempt has a correct-looking but non-matching email/password pair."""
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, error_code="INVALID_CREDENTIALS", status_code=401)

class UnauthorizedException(DomainException):
    """Raised when a request has no token, an invalid/expired token, or references an agent that no longer exists or is inactive."""
    def __init__(self, message: str = "Authentication required or token invalid"):
        super().__init__(message, error_code="UNAUTHORIZED", status_code=401)

class ForbiddenException(DomainException):
    """Raised when an authenticated agent's role or tenant does not permit the requested action."""
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message, error_code="FORBIDDEN", status_code=403)
