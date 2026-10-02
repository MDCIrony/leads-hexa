import pytest

from domain.exceptions import DomainException, ForbiddenException, InvalidUUIDException, UnauthorizedException

_PARAMETERLESS = [
    (InvalidUUIDException, "INVALID_UUID"),
    (UnauthorizedException, "UNAUTHORIZED"),
    (ForbiddenException, "FORBIDDEN"),
]


def test_base_exception_carries_message_and_default_code():
    exc = DomainException("something broke")
    assert (exc.message, exc.error_code) == ("something broke", "DOMAIN_ERROR")


@pytest.mark.parametrize("exception_type,expected_code", _PARAMETERLESS)
def test_each_exception_has_a_stable_error_code(exception_type, expected_code):
    assert exception_type().error_code == expected_code


@pytest.mark.parametrize("exception_type,_", _PARAMETERLESS)
def test_domain_exceptions_do_not_expose_transport_details(exception_type, _):
    """HTTP status codes belong to the adapter, not to the domain."""
    assert not hasattr(exception_type(), "status_code")
