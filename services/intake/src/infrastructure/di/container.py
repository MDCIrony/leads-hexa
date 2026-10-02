import httpx
from chassis.auth import ServiceTokenClient
from chassis.persistence import RawSqlDatabase

from infrastructure.adapters.output.admissions.http_admission_lookup import HttpAdmissionLookup
from infrastructure.adapters.output.admissions.http_lead_admission import HttpLeadAdmission
from infrastructure.adapters.output.admissions.lead_core_client import LeadCoreClient, correlated_post
from infrastructure.adapters.output.parsing.pandas_file_parser import PandasFileParser
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
from infrastructure.config.settings import ApiSettings, WorkerSettings

# The `aud` of the service token lead-core's internal routes accept.
LEAD_CORE_AUDIENCE = "lead-core"
# Admission scores and routes a lead, so it is slower than a plain lookup.
_LEAD_CORE_TIMEOUT_SECONDS = 10.0


class Container:
    """Single place where the process's concrete implementations are chosen.

    Stateless adapters are built once and shared; the unit of work holds a
    transaction, so each caller gets a fresh one. Serves both processes: each
    passes its own settings, and they share every field this reads."""

    def __init__(self, settings: ApiSettings | WorkerSettings) -> None:
        self.settings = settings
        # The pool opens on first use, not here.
        self.database = RawSqlDatabase(settings.database_url)
        self.file_parser = PandasFileParser()
        self._http = httpx.Client(timeout=_LEAD_CORE_TIMEOUT_SECONDS)
        tokens = ServiceTokenClient(
            settings.identity_url.rstrip("/") + "/internal/v1/service-tokens",
            settings.service_client_id, settings.service_client_secret, LEAD_CORE_AUDIENCE,
            post=correlated_post(self._http.post),
        )
        lead_core = LeadCoreClient(settings.lead_core_url, tokens, self._http)
        self.lead_admission = HttpLeadAdmission(lead_core)
        self.admission_lookup = HttpAdmissionLookup(lead_core)

    def unit_of_work(self) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self.database)

    def close(self) -> None:
        self._http.close()
        self.database.close()
