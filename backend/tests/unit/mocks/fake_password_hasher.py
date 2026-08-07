from application.ports.output.password_hasher_port import PasswordHasherPort


class FakePasswordHasher(PasswordHasherPort):
    """Deterministic stand-in. Keeps unit tests free of bcrypt's cost factor,
    which adds ~250ms per call and would dominate the suite's runtime."""

    _PREFIX = "hashed:"

    def hash(self, plain: str) -> str:
        return f"{self._PREFIX}{plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"{self._PREFIX}{plain}"
