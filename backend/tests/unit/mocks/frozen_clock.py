from datetime import datetime

from application.ports.output.clock_port import ClockPort


class FrozenClock(ClockPort):
    """Returns one fixed instant, so tests can assert on timestamps."""

    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant
