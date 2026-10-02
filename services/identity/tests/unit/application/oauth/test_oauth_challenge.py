from hashlib import sha256

import pytest

from application.use_cases.oauth.oauth_challenge import OAuthChallengeUseCase
from domain.exceptions import InvalidCredentialsException
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


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


def test_another_provider_or_state_does_not_consume_the_challenge():
    use_case = OAuthChallengeUseCase(InMemoryUnitOfWork())
    result = use_case.start("GITHUB", "/")

    for provider, state in (("GOOGLE", result.state), ("GITHUB", "forged")):
        with pytest.raises(InvalidCredentialsException):
            use_case.consume(result.nonce, provider, state)
    assert use_case.consume(result.nonce, "GITHUB", result.state).provider == "GITHUB"


@pytest.mark.parametrize("nonce,provider,state", [(None, "GOOGLE", "s"), ("n", "GOOGLE", None), ("n", "FACEBOOK", "s")])
def test_missing_proof_or_an_unknown_provider_is_rejected(nonce, provider, state):
    with pytest.raises(InvalidCredentialsException):
        OAuthChallengeUseCase(InMemoryUnitOfWork()).consume(nonce, provider, state)
