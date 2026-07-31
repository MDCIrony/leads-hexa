from dataclasses import dataclass
from decimal import Decimal
from typing import Union
from domain.exceptions import InvalidBudgetException

@dataclass(frozen=True)
class Money:
    amount: Decimal

    def __init__(self, amount: Union[int, float, str, Decimal]) -> None:
        try:
            dec_amount = Decimal(str(amount))
        except Exception as e:
            raise InvalidBudgetException(f"Valor numérico inválido para Money: '{amount}'") from e

        if dec_amount < Decimal("0"):
            raise InvalidBudgetException(f"El presupuesto no puede ser negativo: {dec_amount}")

        object.__setattr__(self, "amount", dec_amount)

    def __str__(self) -> str:
        return f"{self.amount:.2f}"

    def __float__(self) -> float:
        return float(self.amount)
