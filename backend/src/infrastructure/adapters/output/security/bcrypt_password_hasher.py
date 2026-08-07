from passlib.context import CryptContext

from application.ports.output.password_hasher_port import PasswordHasherPort

# A single shared context avoids re-reading bcrypt's cost-factor config on
# every call.
_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordHasher(PasswordHasherPort):
    def hash(self, plain: str) -> str:
        return _CONTEXT.hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        return _CONTEXT.verify(plain, hashed)
