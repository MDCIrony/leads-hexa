import pytest

from domain.exceptions import (
    DomainException,
    ForbiddenException,
    InvalidBudgetException,
    InvalidEmailException,
    UnauthorizedException,
)


def test_base_exception_carries_message_and_default_code():
    exc = DomainException("something broke")
    assert exc.message == "something broke"
    assert exc.error_code == "DOMAIN_ERROR"


def test_base_exception_accepts_custom_code():
    exc = DomainException("conflict", error_code="ALREADY_EXISTS")
    assert exc.error_code == "ALREADY_EXISTS"


def test_domain_exceptions_do_not_expose_transport_details():
    """HTTP status codes belong to the adapter, not to the domain."""
    for exception_type in (
        DomainException,
        InvalidEmailException,
        InvalidBudgetException,
        UnauthorizedException,
        ForbiddenException,
    ):
        instance = exception_type("msg") if exception_type is DomainException else exception_type()
        assert not hasattr(instance, "status_code"), (
            f"{exception_type.__name__} still carries an HTTP status code"
        )


@pytest.mark.parametrize(
    "exception_type,expected_code",
    [
        (InvalidEmailException, "INVALID_EMAIL"),
        (InvalidBudgetException, "INVALID_BUDGET"),
        (UnauthorizedException, "UNAUTHORIZED"),
        (ForbiddenException, "FORBIDDEN"),
    ],
)
def test_each_exception_has_a_stable_error_code(exception_type, expected_code):
    assert exception_type().error_code == expected_code
