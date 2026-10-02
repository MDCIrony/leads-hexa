from chassis.auth import AUDIENCE, ISSUER, JwksCache, ServiceTokenVerifier, TokenVerifier, load_signers
from chassis.persistence import RawSqlDatabase

from application.ports.output.social import OAuthIdentityProviderPort
from infrastructure.adapters.output.messaging.kafka_credential_provisioner import KafkaCredentialProvisioner
from infrastructure.adapters.output.oauth.providers import (
    GitHubOAuthIdentityProvider, GoogleOAuthIdentityProvider, TestOAuthIdentityProvider,
)
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.adapters.output.security.totp_mfa_crypto import TotpMfaCrypto
from infrastructure.config.settings import ApiSettings
from infrastructure.security.internal_token_issuer import InternalTokenIssuer
from infrastructure.security.service_clients import ServiceClients
from infrastructure.security.service_token_issuer import ServiceTokenIssuer

# The `aud` a service token must carry to open one of identity's own internal routes.
SERVICE_AUDIENCE = "identity"


def _oauth_providers(settings: ApiSettings) -> dict[str, OAuthIdentityProviderPort]:
    providers: dict[str, OAuthIdentityProviderPort] = {}
    if settings.oauth_test_mode:
        providers["GOOGLE"] = TestOAuthIdentityProvider()
    elif settings.google_oauth.enabled:
        providers["GOOGLE"] = GoogleOAuthIdentityProvider(settings.google_oauth)
    if settings.github_oauth.enabled:
        providers["GITHUB"] = GitHubOAuthIdentityProvider(settings.github_oauth)
    return providers


class Container:
    """Single place where the API's concrete implementations are chosen.

    Stateless adapters are built once and shared; the unit of work holds a
    transaction, so each caller gets a fresh one."""

    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings
        # The pool opens on first use, not here.
        self.database = RawSqlDatabase(settings.database_url)
        self.password_hasher = BcryptPasswordHasher()
        self.mfa_crypto = TotpMfaCrypto(settings.mfa_encryption_key)
        self.oauth_providers = _oauth_providers(settings)
        # The internal, unauthenticated listener (ADR-0028), where User:ANONYMOUS is a
        # super.user: this adapter provisions credentials, it does not consume with one.
        self.messaging_provisioner = KafkaCredentialProvisioner(settings.kafka_bootstrap_servers)

        signers = load_signers(settings.signing_keys)
        self.token_issuer = InternalTokenIssuer(signers[0])
        self.service_token_issuer = ServiceTokenIssuer(signers[0], ServiceClients(settings.service_clients))
        self.jwks = {"keys": [signer.public_jwk() for signer in signers]}
        # Identity is the issuer, so it reads its own keys from memory instead of over HTTP.
        keys = JwksCache(lambda: self.jwks)
        self.token_verifier = TokenVerifier(keys, issuer=ISSUER, audience=AUDIENCE)
        self.service_token_verifier = ServiceTokenVerifier(keys, audience=SERVICE_AUDIENCE)

    def unit_of_work(self) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self.database)
