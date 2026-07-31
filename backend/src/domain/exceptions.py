class DomainException(Exception):
    """Excepción base del dominio."""
    pass

class InvalidEmailException(DomainException):
    """Lanzada cuando el formato de email es inválido."""
    pass

class InvalidBudgetException(DomainException):
    """Lanzada cuando el presupuesto o monto es inválido (< 0)."""
    pass

class InvalidUUIDException(DomainException):
    """Lanzada cuando el formato de UUID v4 es inválido."""
    pass

class InvalidRuleException(DomainException):
    """Lanzada cuando una regla o su operador es inválido."""
    pass

class LeadRoutingException(DomainException):
    """Lanzada cuando falla la asignación o enrutamiento del lead."""
    pass
