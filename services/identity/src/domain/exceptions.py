class DomainException(Exception):
    """Base domain exception.

    Carries a stable error_code so that adapters can map it to whatever their
    transport requires. The domain itself knows nothing about HTTP."""

    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class InvalidUUIDException(DomainException):
    """Raised when an identifier is not a well-formed UUID."""

    def __init__(self, message: str = "Formato de UUID inválido"):
        super().__init__(message, error_code="INVALID_UUID")


class AgentNotFoundException(DomainException):
    """Raised when a requested agent id does not exist."""

    def __init__(self, message: str = "Agent not found"):
        super().__init__(message, error_code="AGENT_NOT_FOUND")


class InvalidCredentialsException(DomainException):
    """Raised when an email/password pair does not match an active account."""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, error_code="INVALID_CREDENTIALS")


class InvalidMfaFactorException(InvalidCredentialsException):
    """Generic factor failure, with cookie cleanup metadata for the HTTP adapter."""

    def __init__(self, terminal: bool):
        super().__init__("Invalid authentication factor")
        self.terminal = terminal


class UnauthorizedException(DomainException):
    """Raised when a request carries no valid identity."""

    def __init__(self, message: str = "Authentication required or token invalid"):
        super().__init__(message, error_code="UNAUTHORIZED")


class ForbiddenException(DomainException):
    """Raised when an identity is valid but not permitted to act."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message, error_code="FORBIDDEN")


class InvalidAuthChallengeException(DomainException):
    """Raised when an auth challenge is created outside its contract."""

    def __init__(self, message: str = "Auth challenge is invalid"):
        super().__init__(message, error_code="INVALID_CHALLENGE")


class InvalidSocialIdentityException(DomainException):
    def __init__(self, message: str = "Social identity is invalid"):
        super().__init__(message, error_code="INVALID_SOCIAL_IDENTITY")
