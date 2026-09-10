from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.entities.auth_challenge import AuthChallenge
from tests.unit.mocks.in_memory_uow import InMemoryAuthChallengeRepository


def test_challenge_is_atomic_single_use_and_counts_attempts():
    now = datetime.now(timezone.utc)
    repo = InMemoryAuthChallengeRepository()
    repo.save(AuthChallenge("hash", uuid4(), "LOGIN", 0, now + timedelta(minutes=5), None, now))

    assert repo.resolve_active("hash", now)
    assert repo.increment_attempts("hash", now)
    assert repo.resolve_active("hash", now).attempts == 1
    assert repo.consume("hash", now)
    assert not repo.consume("hash", now)
    assert repo.resolve_active("hash", now) is None
