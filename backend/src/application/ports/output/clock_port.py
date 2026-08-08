import abc
from datetime import datetime


class ClockPort(abc.ABC):
    """Supplies the current instant.

    Injecting time removes the hidden side effect that makes assertions on
    timestamps impossible."""

    @abc.abstractmethod
    def now(self) -> datetime:
        """Return the current instant, always timezone-aware in UTC."""
