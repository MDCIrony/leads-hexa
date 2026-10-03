import uuid
from dataclasses import dataclass
from typing import Optional, Union
from domain.exceptions import InvalidUUIDException

@dataclass(frozen=True)
class TenantId:
    value: uuid.UUID

    def __init__(self, value: Optional[Union[str, uuid.UUID]] = None) -> None:
        if value is None:
            object.__setattr__(self, "value", uuid.uuid4())
        elif isinstance(value, uuid.UUID):
            object.__setattr__(self, "value", value)
        elif isinstance(value, str):
            try:
                object.__setattr__(self, "value", uuid.UUID(value))
            except ValueError as e:
                raise InvalidUUIDException(f"Cadena UUID inválida para TenantId: '{value}'") from e
        else:
            raise InvalidUUIDException(f"Tipo inválido para TenantId: {type(value)}")

    def __str__(self) -> str:
        return str(self.value)
