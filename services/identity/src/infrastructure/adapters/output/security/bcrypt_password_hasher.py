import bcrypt

from application.ports.output.security import PasswordHasherPort

# Cost 12 and the $2b$ prefix are what passlib's bcrypt scheme produced in the backend,
# so the hashes copied from leads_db verify unchanged.
_ROUNDS = 12


class BcryptPasswordHasher(PasswordHasherPort):
    def hash(self, plain: str) -> str:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(_ROUNDS)).decode()

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except ValueError:
            # A stored value that is not a bcrypt hash matches no password.
            return False
