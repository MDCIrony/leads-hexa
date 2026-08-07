import abc


class PasswordHasherPort(abc.ABC):
    """Turns plaintext credentials into an irreversible representation and
    checks a candidate against it. The algorithm is an infrastructure concern."""

    @abc.abstractmethod
    def hash(self, plain: str) -> str:
        """Return an irreversible representation of the plaintext password."""

    @abc.abstractmethod
    def verify(self, plain: str, hashed: str) -> bool:
        """Return True when the plaintext matches the stored representation."""
