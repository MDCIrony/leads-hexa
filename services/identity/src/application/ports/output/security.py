from abc import ABC, abstractmethod


class PasswordHasherPort(ABC):
    """Irreversible credential storage; the algorithm is an infrastructure concern."""

    @abstractmethod
    def hash(self, plain: str) -> str: ...

    @abstractmethod
    def verify(self, plain: str, hashed: str) -> bool: ...
