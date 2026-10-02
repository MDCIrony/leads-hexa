from __future__ import annotations
import abc
from typing import Any

from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.disqualification_rule_repository_port import DisqualificationRuleRepositoryPort
from application.ports.output.sales_group_repository_port import SalesGroupRepositoryPort
from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from application.ports.output.intake_record_repository_port import IntakeRecordRepositoryPort
from application.ports.output.intake_job_repository_port import IntakeJobRepositoryPort
from application.ports.output.outbox_repository_port import OutboxRepositoryPort
from application.ports.output.processed_event_repository_port import ProcessedEventRepositoryPort
from application.ports.output.intake_file_repository_port import IntakeFileRepositoryPort
from application.ports.output.advisors.advisor_repository_port import AdvisorRepositoryPort
from application.ports.output.intake.provisioned_tenant_repository_port import ProvisionedTenantRepositoryPort

class UnitOfWorkPort(abc.ABC):
    leads: LeadRepositoryPort
    rules: RuleRepositoryPort
    disqualification_rules: DisqualificationRuleRepositoryPort
    groups: SalesGroupRepositoryPort
    sources: LeadSourceRepositoryPort
    intake_records: IntakeRecordRepositoryPort
    intake_jobs: IntakeJobRepositoryPort
    outbox: OutboxRepositoryPort
    processed_events: ProcessedEventRepositoryPort
    intake_files: IntakeFileRepositoryPort
    advisors: AdvisorRepositoryPort
    provisioned_tenants: ProvisionedTenantRepositoryPort

    def __enter__(self) -> UnitOfWorkPort:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @abc.abstractmethod
    def commit(self) -> None:
        pass

    @abc.abstractmethod
    def rollback(self) -> None:
        pass
