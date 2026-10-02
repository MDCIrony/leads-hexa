import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class OAuthProviderSettings:
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = ""

    @property
    def enabled(self) -> bool:
        """A half-configured provider is off, never a login button that fails at the callback."""
        if not all((self.client_id.strip(), self.client_secret.strip(), self.redirect_uri.strip())):
            return False
        try:
            uri = urlsplit(self.redirect_uri)
        except ValueError:
            return False
        return (
            not uri.username
            and not uri.password
            and not uri.query
            and not uri.fragment
            and bool(uri.hostname)
            and (uri.scheme == "https" or (uri.scheme == "http" and uri.hostname == "localhost"))
        )

    @classmethod
    def from_environment(cls, prefix: str) -> "OAuthProviderSettings":
        return cls(
            client_id=os.getenv(f"{prefix}_CLIENT_ID", ""),
            client_secret=os.getenv(f"{prefix}_CLIENT_SECRET", ""),
            redirect_uri=os.getenv(f"{prefix}_REDIRECT_URI", ""),
        )


# The deterministic adapter exists solely for a loopback process the HTTP harness
# starts; Settings refuses it outside APP_ENV=test.
TEST_GOOGLE_OAUTH = OAuthProviderSettings(
    "e2e-test-client", "e2e-test-placeholder", "http://localhost/api/v1/auth/oauth/google/callback"
)


def is_origin(value: str) -> bool:
    """Scheme and host (and port) only: what a browser sends in the Origin header."""
    try:
        uri = urlsplit(value)
    except ValueError:
        return False
    return bool(
        uri.scheme in {"http", "https"}
        and uri.hostname
        and not uri.username
        and not uri.password
        and not uri.path
        and not uri.query
        and not uri.fragment
    )
