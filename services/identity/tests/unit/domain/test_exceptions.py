import pytest

from domain.exceptions import (
    AgentNotFoundException,
    DomainException,
    ForbiddenException,
    InvalidAuthChallengeException,
    InvalidCredentialsException,
    InvalidMfaFactorException,
    InvalidSocialIdentityException,
    InvalidUUIDException,
    UnauthorizedException,
)

_PARAMETERLESS = [
    (InvalidUUIDException, "INVALID_UUID"),
    (AgentNotFoundException, "AGENT_NOT_FOUND"),
    (InvalidCredentialsException, "INVALID_CREDENTIALS"),
    (UnauthorizedException, "UNAUTHORIZED"),
    (ForbiddenException, "FORBIDDEN"),
    (InvalidAuthChallengeException, "INVALID_CHALLENGE"),
    (InvalidSocialIdentityException, "INVALID_SOCIAL_IDENTITY"),
]


def test_base_exception_carries_message_and_default_code():
    exc = DomainException("something broke")
    assert exc.message == "something broke"
    assert exc.error_code == "DOMAIN_ERROR"


def test_base_exception_accepts_custom_code():
    assert DomainException("conflict", error_code="ALREADY_EXISTS").error_code == "ALREADY_EXISTS"


@pytest.mark.parametrize("exception_type,expected_code", _PARAMETERLESS)
def test_each_exception_has_a_stable_error_code(exception_type, expected_code):
    assert exception_type().error_code == expected_code


def test_domain_exceptions_do_not_expose_transport_details():
    """HTTP status codes belong to the adapter, not to the domain."""
    for instance in [DomainException("msg"), InvalidMfaFactorException(terminal=False)] + [
        exception_type() for exception_type, _ in _PARAMETERLESS
    ]:
        assert not hasattr(instance, "status_code"), f"{type(instance).__name__} carries an HTTP status"


def test_a_failed_mfa_factor_is_a_credentials_failure_that_says_if_it_is_terminal():
    # Same code as a wrong password, so a caller cannot tell which factor failed.
    exc = InvalidMfaFactorException(terminal=True)
    assert isinstance(exc, InvalidCredentialsException)
    assert exc.error_code == "INVALID_CREDENTIALS"
    assert exc.terminal is True
