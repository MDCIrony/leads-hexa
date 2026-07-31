from dataclasses import dataclass

@dataclass(frozen=True)
class Score:
    value: int = 0

    def add_points(self, delta: int) -> "Score":
        return Score(self.value + delta)

    def subtract_points(self, delta: int) -> "Score":
        return Score(self.value - delta)

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)
