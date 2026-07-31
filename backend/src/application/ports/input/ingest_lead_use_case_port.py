from abc import ABC, abstractmethod
from application.dtos.commands import IngestLeadCommand, LeadProcessedResult

class IngestLeadInputPort(ABC):
    @abstractmethod
    def execute(self, command: IngestLeadCommand) -> LeadProcessedResult:
        pass
