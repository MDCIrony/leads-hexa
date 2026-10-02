class DomainException(Exception):
    """Base domain exception.

    Carries a stable error_code so that adapters can map it to whatever their
    transport requires. The domain itself knows nothing about HTTP."""

    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class ForbiddenException(DomainException):
    """Raised when an identity is valid but not permitted to act."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message, error_code="FORBIDDEN")
