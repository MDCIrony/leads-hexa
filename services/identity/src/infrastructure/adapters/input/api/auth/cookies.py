"""The browser cookies identity owns. Names, paths and lifetimes are part of the
public contract: the frontend and the gateway depend on them as they are."""
from datetime import datetime, timedelta, timezone

from fastapi import Response

from application.dtos.auth import LoginResult
from infrastructure.config.settings import ApiSettings

SESSION_COOKIE = "leads_session"
MFA_CHALLENGE_COOKIE = "leads_mfa_challenge"
OAUTH_CHALLENGE_COOKIE = "leads_oauth_challenge"
# Scoped to the routes that read them, so no other request carries a challenge.
MFA_CHALLENGE_PATH = "/api/v1/auth/mfa"
OAUTH_CHALLENGE_PATH = "/api/v1/auth/oauth"
_CHALLENGE_MINUTES = 5


def _set(response: Response, name: str, value: str, path: str, lifetime: timedelta, settings: ApiSettings) -> None:
    response.set_cookie(
        name, value, httponly=True, samesite="lax", secure=settings.session_cookie_secure, path=path,
        max_age=int(lifetime.total_seconds()), expires=datetime.now(timezone.utc) + lifetime,
    )


def set_session(response: Response, token: str, settings: ApiSettings) -> None:
    _set(response, SESSION_COOKIE, token, "/", timedelta(hours=settings.session_hours), settings)


def set_mfa_challenge(response: Response, token: str, settings: ApiSettings) -> None:
    _set(response, MFA_CHALLENGE_COOKIE, token, MFA_CHALLENGE_PATH, timedelta(minutes=_CHALLENGE_MINUTES), settings)


def set_oauth_challenge(response: Response, nonce: str, settings: ApiSettings) -> None:
    _set(response, OAUTH_CHALLENGE_COOKIE, nonce, OAUTH_CHALLENGE_PATH, timedelta(minutes=_CHALLENGE_MINUTES), settings)


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def clear_mfa_challenge(response: Response) -> None:
    response.delete_cookie(MFA_CHALLENGE_COOKIE, path=MFA_CHALLENGE_PATH)


def clear_oauth_challenge(response: Response) -> None:
    response.delete_cookie(OAUTH_CHALLENGE_COOKIE, path=OAUTH_CHALLENGE_PATH)


def apply_login(response: Response, result: LoginResult, settings: ApiSettings) -> None:
    """A full session, or only the MFA challenge: never both, and never a stale one left behind."""
    if result.status == "AUTHENTICATED":
        clear_mfa_challenge(response)
        set_session(response, result.token, settings)
    else:
        clear_session(response)
        set_mfa_challenge(response, result.token, settings)
