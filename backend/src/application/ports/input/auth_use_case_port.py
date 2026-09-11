from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from application.use_cases.auth_use_cases import LoginResult


class LoginInputPort(ABC):
    @abstractmethod
    def execute(self, email: str, password: str) -> LoginResult:
        pass
