from datetime import datetime, timezone

from application.ports.output.clock_port import ClockPort


class SystemClock(ClockPort):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
