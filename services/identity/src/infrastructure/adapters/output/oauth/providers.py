import httpx

from application.ports.output.social import (
    OAuthIdentity, OAuthIdentityProviderError, OAuthIdentityProviderPort,
)
from infrastructure.config.oauth import OAuthProviderSettings


class _HttpxOAuthIdentityProvider(OAuthIdentityProviderPort):
    timeout_seconds = 5.0

    def __init__(self, settings: OAuthProviderSettings) -> None:
        self.settings = settings

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise OAuthIdentityProviderError()
        return data

    @staticmethod
    def _json_list(response: httpx.Response) -> list[dict]:
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise OAuthIdentityProviderError()
        return data

    def _token(self, client: httpx.Client, endpoint: str, code: str, pkce_verifier: str) -> str:
        try:
            data = self._json(client.post(endpoint, data={
                "code": code,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "redirect_uri": self.settings.redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": pkce_verifier,
            }, headers={"Accept": "application/json"}))
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise OAuthIdentityProviderError()
            return token
        except (httpx.HTTPError, ValueError, TypeError, OAuthIdentityProviderError):
            raise OAuthIdentityProviderError() from None


class GoogleOAuthIdentityProvider(_HttpxOAuthIdentityProvider):
    def exchange(self, code: str, pkce_verifier: str) -> OAuthIdentity:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                token = self._token(client, "https://oauth2.googleapis.com/token", code, pkce_verifier)
                data = self._json(client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                ))
            subject, email = data.get("sub"), data.get("email")
            if not isinstance(subject, str) or not subject or not isinstance(email, str) or not email or data.get("email_verified") is not True:
                raise OAuthIdentityProviderError()
            return OAuthIdentity(subject, email, True, data.get("name") if isinstance(data.get("name"), str) else None)
        except (httpx.HTTPError, ValueError, TypeError, OAuthIdentityProviderError):
            raise OAuthIdentityProviderError() from None


class GitHubOAuthIdentityProvider(_HttpxOAuthIdentityProvider):
    def exchange(self, code: str, pkce_verifier: str) -> OAuthIdentity:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                token = self._token(client, "https://github.com/login/oauth/access_token", code, pkce_verifier)
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
                user = self._json(client.get("https://api.github.com/user", headers=headers))
                emails = self._json_list(client.get("https://api.github.com/user/emails", headers=headers))
            subject = user.get("id")
            email = next((item.get("email") for item in emails if isinstance(item, dict) and item.get("primary") is True and item.get("verified") is True and isinstance(item.get("email"), str)), None)
            if subject is None or not str(subject) or not isinstance(email, str) or not email:
                raise OAuthIdentityProviderError()
            name = user.get("name") or user.get("login")
            return OAuthIdentity(str(subject), email, True, name if isinstance(name, str) else None)
        except (httpx.HTTPError, ValueError, TypeError, OAuthIdentityProviderError):
            raise OAuthIdentityProviderError() from None


class TestOAuthIdentityProvider(OAuthIdentityProviderPort):
    """Deterministic identity double, available only with APP_ENV=test."""

    def exchange(self, code: str, pkce_verifier: str) -> OAuthIdentity:
        try:
            email, verified, subject = code.split("|", 2)
            if not email or not subject or verified not in {"verified", "unverified"}:
                raise ValueError
        except ValueError:
            raise OAuthIdentityProviderError() from None
        return OAuthIdentity(subject, email, verified == "verified", "OAuth E2E")
