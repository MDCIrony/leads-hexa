from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.exceptions import InvalidSocialIdentityException
from domain.social.social_identity import SocialIdentity

_NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def _identity(provider="GOOGLE", subject="sub-1", email="ana@acme.test"):
    return SocialIdentity(uuid4(), uuid4(), provider, subject, email, _NOW, _NOW)


def test_a_complete_identity_of_a_supported_provider_is_accepted():
    assert _identity(provider="GITHUB").provider_subject == "sub-1"


def test_an_unsupported_provider_is_rejected():
    with pytest.raises(InvalidSocialIdentityException):
        _identity(provider="FACEBOOK")


@pytest.mark.parametrize("subject,email", [("  ", "ana@acme.test"), ("sub-1", "")])
def test_an_incomplete_identity_is_rejected(subject, email):
    with pytest.raises(InvalidSocialIdentityException):
        _identity(subject=subject, email=email)
