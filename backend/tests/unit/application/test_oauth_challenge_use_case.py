from hashlib import sha256

import pytest

from application.use_cases.auth_use_cases import OAuthChallengeUseCase
from domain.exceptions import InvalidCredentialsException
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def test_oauth_challenge_binds_provider_state_cookie_and_can_only_be_consumed_once():
    uow = InMemoryUnitOfWork()
    use_case = OAuthChallengeUseCase(uow)

    result = use_case.start("GOOGLE", "/mis-leads")
    challenge = use_case.consume(result.nonce, "GOOGLE", result.state)

    assert len(result.nonce) >= 43 and len(result.state) >= 43 and 43 <= len(result.pkce_verifier) <= 128
    assert challenge.return_path == "/mis-leads"
    assert sha256(result.nonce.encode()).hexdigest() in uow.challenges.items
    with pytest.raises(InvalidCredentialsException):
        use_case.consume(result.nonce, "GOOGLE", result.state)
    with pytest.raises(InvalidCredentialsException):
        use_case.start("GOOGLE", "//other.test")
