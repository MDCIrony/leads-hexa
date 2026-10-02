from datetime import datetime
from hashlib import sha1

import pyotp
from cryptography.fernet import Fernet

from application.ports.output.mfa import MfaCryptoPort


class TotpMfaCrypto(MfaCryptoPort):
    """TOTP compatibility policy lives here; the application only sees steps."""

    _INTERVAL = 30

    def __init__(self, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())

    def generate_secret(self) -> str:
        return pyotp.random_base32(length=32)

    def encrypt(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def matching_step(self, secret: str, code: str, now: datetime) -> int | None:
        totp = self._totp(secret)
        current_step = int(now.timestamp()) // self._INTERVAL
        # One step either side: the clock of an authenticator app drifts.
        for step in range(current_step - 1, current_step + 2):
            if totp.verify(code, for_time=step * self._INTERVAL):
                return step
        return None

    def provisioning_uri(self, secret: str, email: str) -> str:
        return self._totp(secret).provisioning_uri(name=email, issuer_name="Lead Router")

    def _totp(self, secret: str) -> pyotp.TOTP:
        return pyotp.TOTP(secret, digits=6, interval=self._INTERVAL, digest=sha1)
