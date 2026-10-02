from collections.abc import Callable

import httpx
from chassis.auth import (AUDIENCE, ISSUER, JwksCache, ServiceTokenClient, ServiceTokenVerifier, TokenVerifier,
                          http_jwks)
from chassis.web import request_id_var
from application.ports.output.advisors.advisor_directory_port import AdvisorDirectoryPort
from application.ports.output.clock_port import ClockPort
from application.ports.output.id_generator_port import IdGeneratorPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.services.assignment_engine import AssignmentEngine
from infrastructure.adapters.output.http.advisors.http_identity_agents import HttpIdentityAgents
from infrastructure.adapters.output.persistence.advisors.hydrating_advisor_directory import HydratingAdvisorDirectory
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.system_clock import SystemClock
from infrastructure.adapters.output.uuid_generator import UuidGenerator
from infrastructure.config.settings import Settings


def _correlated(post: Callable[..., httpx.Response]) -> Callable[..., httpx.Response]:
    """The token request carries the caller's request id, like the call it precedes."""
    return lambda url, **kwargs: post(url, headers={"X-Request-Id": request_id_var.get()}, **kwargs)


class Container:
    """Single place where concrete implementations are chosen and their
    lifetimes decided.

    Stateless adapters are built once and shared; anything holding
    per-transaction state is built on demand. Getting this wrong is what makes
    a round-robin cursor reset on every request."""

    def __init__(self, settings: Settings, jwks_fetch: Callable[[], dict] | None = None) -> None:
        self._settings = settings
        self._database = RawSqlDatabase(dsn=settings.database_url)
        self._clock = SystemClock()
        self._id_generator = UuidGenerator()
        # The engine is stateless (the rotation cursor lives on the
        # persisted rule instead of in memory), so it no longer needs to be
        # a singleton for correctness; kept as one anyway since there is no
        # reason not to.
        self._assignment_engine = AssignmentEngine()
        # Lazy: the first verification fetches the keys, not construction.
        jwks = JwksCache(jwks_fetch or http_jwks(settings.jwks_url))
        self._token_verifier = TokenVerifier(jwks, issuer=ISSUER, audience=AUDIENCE)
        # Same keys, other audience: what intake calls /internal/v1/admissions with.
        self._service_token_verifier = ServiceTokenVerifier(jwks, audience="lead-core")
        # Built once: the token client caches its token, the HTTP client its connections.
        self._identity_http = httpx.Client(timeout=2.0)
        tokens = ServiceTokenClient(settings.identity_url.rstrip("/") + "/internal/v1/service-tokens",
                                    settings.service_client_id, settings.service_client_secret, "identity",
                                    post=_correlated(self._identity_http.post))
        self._advisor_directory = HydratingAdvisorDirectory(
            self.unit_of_work, HttpIdentityAgents(settings.identity_url, tokens, self._identity_http))

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def database(self) -> RawSqlDatabase:
        return self._database

    @property
    def token_verifier(self) -> TokenVerifier:
        return self._token_verifier

    @property
    def service_token_verifier(self) -> ServiceTokenVerifier:
        return self._service_token_verifier

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
    def advisor_directory(self) -> AdvisorDirectoryPort:
        return self._advisor_directory

    def close(self) -> None:
        self._identity_http.close()
        self._database.close()

    def unit_of_work(self) -> UnitOfWorkPort:
        """A fresh unit of work per call: it owns a transaction, which must not
        be shared between requests."""
        return PostgresUnitOfWork(self._database)
