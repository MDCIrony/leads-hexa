from application.ports.output.clock_port import ClockPort
from application.ports.output.file_parser_port import FileParserPort
from application.ports.output.id_generator_port import IdGeneratorPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.token_service_port import TokenServicePort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.services.router_engine import RouterEngine
from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from infrastructure.adapters.output.system_clock import SystemClock
from infrastructure.adapters.output.uuid_generator import UuidGenerator
from infrastructure.config.settings import Settings


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
        self._token_service = JwtTokenService(
            secret=settings.jwt_secret,
            expires_minutes=settings.jwt_expires_minutes,
        )
        self._clock = SystemClock()
        self._id_generator = UuidGenerator()
        # Built once and shared: its round-robin index must survive across
        # requests, or every routing decision would land on the same agent.
        self._assignment_engine = RouterEngine()
        self._file_parser = PandasFileParser()
        self._event_publisher = InMemoryEventPublisher()

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
    def token_service(self) -> TokenServicePort:
        return self._token_service

    @property
    def clock(self) -> ClockPort:
        return self._clock

    @property
    def id_generator(self) -> IdGeneratorPort:
        return self._id_generator

    @property
    def assignment_engine(self) -> RouterEngine:
        return self._assignment_engine

    @property
    def file_parser(self) -> FileParserPort:
        return self._file_parser

    @property
    def event_publisher(self) -> InMemoryEventPublisher:
        return self._event_publisher

    def unit_of_work(self) -> UnitOfWorkPort:
        """A fresh unit of work per call: it owns a transaction, which must not
        be shared between requests."""
        return PostgresUnitOfWork(self._database)
