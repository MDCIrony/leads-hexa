from datetime import datetime, timezone
from uuid import UUID

from application.ports.output.clock_port import ClockPort
from application.ports.output.id_generator_port import IdGeneratorPort
from infrastructure.adapters.output.system_clock import SystemClock
from infrastructure.adapters.output.uuid_generator import UuidGenerator
from tests.unit.mocks.frozen_clock import FrozenClock


def test_system_clock_satisfies_the_port():
    assert isinstance(SystemClock(), ClockPort)


def test_system_clock_returns_timezone_aware_utc():
    """A naive datetime would compare incorrectly against stored timestamps."""
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_frozen_clock_always_returns_the_same_instant():
    instant = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)
    clock = FrozenClock(instant)
    assert clock.now() == instant
    assert clock.now() == instant


def test_uuid_generator_satisfies_the_port():
    assert isinstance(UuidGenerator(), IdGeneratorPort)


def test_uuid_generator_returns_distinct_uuids():
    generator = UuidGenerator()
    first, second = generator.new_id(), generator.new_id()
    assert isinstance(first, UUID)
    assert first != second
