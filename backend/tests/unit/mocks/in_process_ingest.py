from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from infrastructure.adapters.output.admissions.in_process_lead_admission import InProcessLeadAdmission


def in_process_ingest(uow: UnitOfWorkPort) -> IngestLeadUseCase:
    """The monolith's wiring before the cut: both halves over the same unit of work."""
    return IngestLeadUseCase(uow=uow, admission=InProcessLeadAdmission(lambda: uow))
