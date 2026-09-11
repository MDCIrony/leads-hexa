from abc import ABC, abstractmethod
from datetime import datetime


class MfaCryptoPort(ABC):
    @abstractmethod
    def generate_secret(self) -> str: ...

    @abstractmethod
    def encrypt(self, secret: str) -> str: ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str: ...

    @abstractmethod
    def matching_step(self, secret: str, code: str, now: datetime) -> int | None: ...

    @abstractmethod
    def provisioning_uri(self, secret: str, email: str) -> str: ...
