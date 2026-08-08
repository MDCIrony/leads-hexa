import abc
from uuid import UUID


class IdGeneratorPort(abc.ABC):
    """Supplies fresh entity identifiers."""

    @abc.abstractmethod
    def new_id(self) -> UUID:
        """Return a new unique identifier."""
