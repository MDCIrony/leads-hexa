from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from domain.exceptions import InvalidAuthChallengeException
from domain.sessions.auth_challenge import AuthChallenge

_NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
_OAUTH = {"provider": "GOOGLE", "state_hash": "state", "pkce_verifier": "verifier", "return_path": "/home"}


def _challenge(purpose="LOGIN", attempts=0, token_hash="hash", agent_id=None, **oauth):
    return AuthChallenge(
        token_hash, agent_id, purpose, attempts, _NOW + timedelta(minutes=5), None, _NOW, **oauth
    )


def test_a_login_challenge_is_created_with_its_fields():
    agent_id = uuid4()
    challenge = _challenge(agent_id=agent_id)
    assert (challenge.token_hash, challenge.agent_id, challenge.purpose) == ("hash", agent_id, "LOGIN")
    assert challenge.attempts == 0 and challenge.consumed_at is None


@pytest.mark.parametrize("purpose", ["", "   "])
def test_an_empty_purpose_is_rejected_at_creation(purpose):
    with pytest.raises(InvalidAuthChallengeException):
        _challenge(purpose=purpose)


def test_negative_attempts_are_rejected_at_creation():
    with pytest.raises(InvalidAuthChallengeException):
        _challenge(attempts=-1)


def test_validation_errors_carry_no_secret():
    with pytest.raises(InvalidAuthChallengeException) as empty:
        _challenge(purpose="", token_hash="s3cr3t-token-hash")
    with pytest.raises(InvalidAuthChallengeException) as negative:
        _challenge(attempts=-1, token_hash="s3cr3t-token-hash")

    assert "s3cr3t" not in str(empty.value)
    assert "s3cr3t" not in str(negative.value)


def test_an_oauth_challenge_requires_its_metadata():
    with pytest.raises(InvalidAuthChallengeException):
        _challenge(purpose="OAUTH_LOGIN")
    with pytest.raises(InvalidAuthChallengeException):
        _challenge(purpose="OAUTH_LOGIN", **{**_OAUTH, "provider": "FACEBOOK"})


def test_only_an_oauth_challenge_may_carry_oauth_data():
    with pytest.raises(InvalidAuthChallengeException):
        _challenge(purpose="MFA_LOGIN", return_path="/home")


@pytest.mark.parametrize(
    "return_path", ["//other.test", "https://other.test", "/home?next=x", "/home#top", "/home\\other", "/home\x00"]
)
def test_an_oauth_challenge_rejects_non_internal_return_paths(return_path):
    with pytest.raises(InvalidAuthChallengeException):
        _challenge(purpose="OAUTH_LOGIN", **{**_OAUTH, "return_path": return_path})


def test_an_oauth_challenge_matches_only_its_own_provider_and_state():
    challenge = _challenge(purpose="OAUTH_LOGIN", **_OAUTH)

    assert challenge.matches_oauth("GOOGLE", "state") is True
    assert challenge.matches_oauth("GOOGLE", "other") is False
    assert challenge.matches_oauth("GITHUB", "state") is False
    assert _challenge().matches_oauth("GOOGLE", "state") is False
