from chassis.auth import JwksCache, TokenVerifier, load_signers
from application.ports.output.clock_port import ClockPort
from application.ports.output.file_parser_port import FileParserPort
from application.ports.output.id_generator_port import IdGeneratorPort
from application.ports.output.job_queue_port import JobQueuePort
from application.ports.output.messaging_credential_provisioner_port import MessagingCredentialProvisionerPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.oauth_identity_provider_port import OAuthIdentityProviderPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.services.assignment_engine import AssignmentEngine
from infrastructure.adapters.output.events.kafka_credential_provisioner import KafkaCredentialProvisioner
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.queue.rabbitmq_job_queue import RabbitMQJobQueue
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.adapters.output.security.totp_mfa_crypto import TotpMfaCrypto
from infrastructure.adapters.output.http.oauth_identity_providers import (
    GitHubOAuthIdentityProvider, GoogleOAuthIdentityProvider, TestOAuthIdentityProvider,
)
from infrastructure.adapters.output.system_clock import SystemClock
from infrastructure.adapters.output.uuid_generator import UuidGenerator
from infrastructure.config.settings import Settings
from infrastructure.security.internal_token_issuer import InternalTokenIssuer


class Container:
    """Single place where concrete implementations are chosen and their
    lifetimes decided.

    Stateless adapters are built once and shared; anything holding
    per-transaction state is built on demand. Getting this wrong is what makes
    a round-robin cursor reset on every request."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._database = RawSqlDatabase(dsn=settings.database_url)
        self._password_hasher = BcryptPasswordHasher()
        self._mfa_crypto = TotpMfaCrypto(settings.mfa_encryption_key)
        self._clock = SystemClock()
        self._id_generator = UuidGenerator()
        # The engine is stateless (the rotation cursor lives on the
        # persisted rule instead of in memory), so it no longer needs to be
        # a singleton for correctness; kept as one anyway since there is no
        # reason not to.
        self._assignment_engine = AssignmentEngine()
        self._file_parser = PandasFileParser()
        # Safe to build eagerly: connecting happens per enqueue call, not at
        # construction (ADR-0027), so a RabbitMQ outage never blocks startup.
        self._job_queue = RabbitMQJobQueue(settings.rabbitmq_url)
        # The internal, unauthenticated listener (ADR-0028): the same one
        # KafkaOutboundDispatcher uses, where User:ANONYMOUS is a super.user,
        # not the SASL one the host reaches — this adapter is the thing
        # provisioning credentials, not a tenant consuming with one.
        self._messaging_credential_provisioner = KafkaCredentialProvisioner(settings.kafka_bootstrap_servers)
        signers = load_signers(settings.signing_keys)
        self._token_issuer = InternalTokenIssuer(signers[0])
        self._jwks = {"keys": [signer.public_jwk() for signer in signers]}
        # In F0 this process is both issuer and verifier, so it reads its own
        # keys from memory instead of fetching them over HTTP.
        self._token_verifier = TokenVerifier(
            JwksCache(lambda: self._jwks),
            issuer=InternalTokenIssuer.ISSUER,
            audience=InternalTokenIssuer.AUDIENCE,
        )
        self._oauth_identity_providers: dict[str, OAuthIdentityProviderPort] = {}
        if settings.oauth_test_mode:
            self._oauth_identity_providers["GOOGLE"] = TestOAuthIdentityProvider()
        elif settings.google_oauth.enabled:
            self._oauth_identity_providers["GOOGLE"] = GoogleOAuthIdentityProvider(settings.google_oauth)
        if settings.github_oauth.enabled:
            self._oauth_identity_providers["GITHUB"] = GitHubOAuthIdentityProvider(settings.github_oauth)

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def database(self) -> RawSqlDatabase:
        return self._database

    @property
    def password_hasher(self) -> PasswordHasherPort:
        return self._password_hasher

    @property
    def mfa_crypto(self) -> TotpMfaCrypto:
        return self._mfa_crypto

    @property
    def token_issuer(self) -> InternalTokenIssuer:
        return self._token_issuer

    @property
    def token_verifier(self) -> TokenVerifier:
        return self._token_verifier

    @property
    def jwks(self) -> dict:
        return self._jwks

    @property
    def clock(self) -> ClockPort:
        return self._clock

    @property
    def id_generator(self) -> IdGeneratorPort:
        return self._id_generator

    @property
    def assignment_engine(self) -> AssignmentEngine:
        return self._assignment_engine

    @property
    def file_parser(self) -> FileParserPort:
        return self._file_parser

    @property
    def job_queue(self) -> JobQueuePort:
        return self._job_queue

    @property
    def messaging_credential_provisioner(self) -> MessagingCredentialProvisionerPort:
        return self._messaging_credential_provisioner

    def oauth_identity_provider(self, provider: str) -> OAuthIdentityProviderPort | None:
        return self._oauth_identity_providers.get(provider)

    @property
    def oauth_providers(self) -> list[str]:
        return list(self._oauth_identity_providers)

    def unit_of_work(self) -> UnitOfWorkPort:
        """A fresh unit of work per call: it owns a transaction, which must not
        be shared between requests."""
        return PostgresUnitOfWork(self._database)
