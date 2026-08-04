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
