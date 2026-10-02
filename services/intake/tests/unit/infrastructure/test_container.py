import pytest

from infrastructure.adapters.output.admissions.http_admission_lookup import HttpAdmissionLookup
from infrastructure.adapters.output.admissions.http_lead_admission import HttpLeadAdmission
from infrastructure.adapters.output.parsing.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
from infrastructure.config.settings import ApiSettings, WorkerSettings
from infrastructure.di.container import Container

_API = ApiSettings(
    database_url="postgresql://u:p@nowhere:5432/db", jwks_url="http://identity/jwks",
    lead_core_url="http://lead-core", service_client_secret="s3cret",
)
_WORKER = WorkerSettings(
    database_url="postgresql://u:p@nowhere:5432/db", lead_core_url="http://lead-core",
    service_client_secret="s3cret", rabbitmq_url="amqp://nowhere", kafka_bootstrap_servers="nowhere:9092",
)


@pytest.mark.parametrize("settings", [_API, _WORKER], ids=["api", "worker"])
def test_both_processes_get_the_same_adapters_without_reaching_anything(settings):
    container = Container(settings)

    assert isinstance(container.lead_admission, HttpLeadAdmission)
    assert isinstance(container.admission_lookup, HttpAdmissionLookup)
    assert isinstance(container.file_parser, PandasFileParser)
    container.close()


def test_every_caller_gets_its_own_unit_of_work_over_the_shared_pool():
    container = Container(_API)

    first, second = container.unit_of_work(), container.unit_of_work()

    assert isinstance(first, PostgresUnitOfWork) and first is not second
    container.close()


def test_only_the_api_verifies_tokens():
    api, worker = Container(_API), Container(_WORKER)

    assert api.token_verifier is not None
    assert worker.token_verifier is None
    api.close()
    worker.close()
