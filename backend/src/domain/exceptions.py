class DomainException(Exception):
    """Excepción base del dominio."""
    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

class InvalidEmailException(DomainException):
    """Lanzada cuando el formato de email es inválido."""
    def __init__(self, message: str = "Formato de correo electrónico inválido"):
        super().__init__(message, error_code="INVALID_EMAIL")

class InvalidBudgetException(DomainException):
    """Lanzada cuando el presupuesto o monto es inválido (< 0)."""
    def __init__(self, message: str = "Presupuesto inválido"):
        super().__init__(message, error_code="INVALID_BUDGET")

class InvalidUUIDException(DomainException):
    """Lanzada cuando el formato de UUID v4 es inválido."""
    def __init__(self, message: str = "Formato de UUID inválido"):
        super().__init__(message, error_code="INVALID_UUID")

class InvalidRuleException(DomainException):
    """Lanzada cuando una regla o su operador es inválido."""
    def __init__(self, message: str = "Regla de scoring o routing inválida"):
        super().__init__(message, error_code="INVALID_RULE")

class LeadRoutingException(DomainException):
    """Lanzada cuando falla la asignación o enrutamiento del lead."""
    def __init__(self, message: str = "Fallo en el enrutamiento del lead"):
        super().__init__(message, error_code="ROUTING_FAILED")
