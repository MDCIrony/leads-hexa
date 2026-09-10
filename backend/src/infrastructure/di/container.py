from application.ports.output.clock_port import ClockPort
from application.ports.output.file_parser_port import FileParserPort
from application.ports.output.id_generator_port import IdGeneratorPort
from application.ports.output.job_queue_port import JobQueuePort
from application.ports.output.messaging_credential_provisioner_port import MessagingCredentialProvisionerPort
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.services.assignment_engine import AssignmentEngine
from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.adapters.output.events.kafka_credential_provisioner import KafkaCredentialProvisioner
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.queue.rabbitmq_job_queue import RabbitMQJobQueue
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
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
        self._clock = SystemClock()
        self._id_generator = UuidGenerator()
        # The engine is stateless (the rotation cursor lives on the
        # persisted rule instead of in memory), so it no longer needs to be
        # a singleton for correctness; kept as one anyway since there is no
        # reason not to.
        self._assignment_engine = AssignmentEngine()
        self._file_parser = PandasFileParser()
        self._event_publisher = InMemoryEventPublisher()
        # Safe to build eagerly: connecting happens per enqueue call, not at
        # construction (ADR-0027), so a RabbitMQ outage never blocks startup.
        self._job_queue = RabbitMQJobQueue(settings.rabbitmq_url)
        # The internal, unauthenticated listener (ADR-0028): the same one
        # KafkaOutboundDispatcher uses, where User:ANONYMOUS is a super.user,
        # not the SASL one the host reaches — this adapter is the thing
        # provisioning credentials, not a tenant consuming with one.
        self._messaging_credential_provisioner = KafkaCredentialProvisioner(settings.kafka_bootstrap_servers)

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
    def event_publisher(self) -> InMemoryEventPublisher:
        return self._event_publisher

    @property
    def job_queue(self) -> JobQueuePort:
        return self._job_queue

    @property
    def messaging_credential_provisioner(self) -> MessagingCredentialProvisionerPort:
        return self._messaging_credential_provisioner

    def unit_of_work(self) -> UnitOfWorkPort:
        """A fresh unit of work per call: it owns a transaction, which must not
        be shared between requests."""
        return PostgresUnitOfWork(self._database)
