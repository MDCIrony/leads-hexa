from domain.exceptions import (
    DomainException,
    InvalidEmailException,
    InvalidBudgetException,
    InvalidUUIDException,
    InvalidRuleException,
    LeadRoutingException,
)


def test_domain_exception_defaults_to_400():
    exc = DomainException("generic failure")
    assert exc.status_code == 400
    assert exc.error_code == "DOMAIN_ERROR"


def test_domain_exception_accepts_custom_status_code():
    exc = DomainException("custom failure", error_code="CUSTOM", status_code=409)
    assert exc.status_code == 409
    assert exc.error_code == "CUSTOM"


def test_existing_subclasses_default_to_400():
    for exc in (
        InvalidEmailException(),
        InvalidBudgetException(),
        InvalidUUIDException(),
        InvalidRuleException(),
        LeadRoutingException(),
    ):
        assert exc.status_code == 400
