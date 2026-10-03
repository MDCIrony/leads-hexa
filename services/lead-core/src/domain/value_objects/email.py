import re
from dataclasses import dataclass
from domain.exceptions import InvalidEmailException

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

@dataclass(frozen=True)
class EmailAddress:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not EMAIL_REGEX.match(self.value):
            raise InvalidEmailException(f"Formato de correo electrónico inválido: '{self.value}'")

    def __str__(self) -> str:
        return self.value
