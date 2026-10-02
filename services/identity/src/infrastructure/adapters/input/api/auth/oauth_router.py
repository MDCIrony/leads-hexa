from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from application.ports.input.oauth import OAuthChallengeInputPort, SocialLoginInputPort
from application.ports.output.social import OAuthIdentityProviderPort
from domain.exceptions import InvalidCredentialsException, InvalidMfaFactorException
from infrastructure.adapters.input.api.auth import cookies
from infrastructure.adapters.input.api.auth.schemas import OAuthProvidersResponse
from infrastructure.adapters.input.api.dependencies import get_container
from infrastructure.adapters.input.api.use_case_factories import (
    get_oauth_challenge_use_case, get_social_login_use_case,
)
from infrastructure.di.container import Container

router = APIRouter(prefix="/oauth")

_AUTHORIZATION = {
    "GOOGLE": ("https://accounts.google.com/o/oauth2/v2/auth", "openid email profile"),
    "GITHUB": ("https://github.com/login/oauth/authorize", "read:user user:email"),
}
_REDIRECT = {"status_code": status.HTTP_303_SEE_OTHER, "response_class": RedirectResponse}


def _enabled_provider(value: str, container: Container) -> tuple[str, OAuthIdentityProviderPort]:
    provider = value.upper()
    identity_provider = container.oauth_providers.get(provider) if provider in _AUTHORIZATION else None
    if identity_provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no disponible")
    return provider, identity_provider


def _redirect(location: str) -> RedirectResponse:
    return RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/providers", response_model=OAuthProvidersResponse)
def oauth_providers(response: Response, container: Container = Depends(get_container)):
    # Dynamic per configuration: a cached "[]" would hide buttons that a
    # later-configured provider should show.
    response.headers["Cache-Control"] = "no-store"
    return OAuthProvidersResponse(providers=list(container.oauth_providers))


@router.get("/{provider}/start", **_REDIRECT, responses={303: {"description": "Redirección al proveedor OAuth"}})
def start_oauth_login(
    provider: str,
    return_path: str = "/",
    use_case: OAuthChallengeInputPort = Depends(get_oauth_challenge_use_case),
    container: Container = Depends(get_container),
):
    provider, _ = _enabled_provider(provider, container)
    try:
        challenge = use_case.start(provider, return_path)
    except InvalidCredentialsException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ruta de retorno inválida") from None

    endpoint, scope = _AUTHORIZATION[provider]
    settings = container.settings
    client = settings.google_oauth if provider == "GOOGLE" else settings.github_oauth
    code_challenge = urlsafe_b64encode(sha256(challenge.pkce_verifier.encode()).digest()).rstrip(b"=").decode()
    parameters = urlencode({
        "response_type": "code", "client_id": client.client_id,
        "redirect_uri": client.redirect_uri, "scope": scope, "state": challenge.state,
        "code_challenge": code_challenge, "code_challenge_method": "S256",
    })
    response = _redirect(f"{endpoint}?{parameters}")
    cookies.set_oauth_challenge(response, challenge.nonce, settings)
    return response


@router.get("/{provider}/callback", **_REDIRECT, responses={303: {"description": "Redirección tras OAuth"}})
def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    challenge_use_case: OAuthChallengeInputPort = Depends(get_oauth_challenge_use_case),
    social_login: SocialLoginInputPort = Depends(get_social_login_use_case),
    container: Container = Depends(get_container),
):
    settings = container.settings
    # Every failure, whatever its cause, ends on the same generic page: the URL
    # must not tell an attacker which check stopped them.
    try:
        provider, identity_provider = _enabled_provider(provider, container)
        if not code:
            raise InvalidMfaFactorException(terminal=True)
        challenge = challenge_use_case.consume(request.cookies.get(cookies.OAUTH_CHALLENGE_COOKIE), provider, state)
        identity = identity_provider.exchange(code, challenge.pkce_verifier or "")
        result = social_login.execute(provider, identity.provider_subject, identity.email, identity.email_verified)
    except Exception:
        response = _redirect(f"{settings.frontend_origin}/login?oauth_error=1")
        cookies.clear_oauth_challenge(response)
        return response

    target = "/mfa" if result.status == "MFA_REQUIRED" else challenge.return_path
    response = _redirect(f"{settings.frontend_origin}{target}")
    cookies.apply_login(response, result, settings)
    cookies.clear_oauth_challenge(response)
    return response
