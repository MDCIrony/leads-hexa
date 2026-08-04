from abc import ABC, abstractmethod


class LoginInputPort(ABC):
    @abstractmethod
    def execute(self, email: str, password: str) -> str:
        pass
