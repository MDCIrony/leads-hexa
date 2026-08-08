from abc import ABC, abstractmethod
from typing import List
from uuid import UUID
from application.dtos.commands import IngestLeadCommand

class FileParserPort(ABC):
    @abstractmethod
    def parse_leads_file(
        self, file_content: bytes, filename: str, tenant_id: UUID, source_id: UUID
    ) -> List[IngestLeadCommand]:
        """Parsea un archivo CSV o XLSX en una colección de IngestLeadCommand."""
        pass
