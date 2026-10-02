from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from application.dtos.reception import IngestLeadCommand


class FileParserPort(ABC):
    @abstractmethod
    def parse_leads_file(
        self, file_content: bytes, filename: str, tenant_id: UUID, source_id: UUID
    ) -> List[IngestLeadCommand]:
        """Parses a CSV or XLSX file into one command per row."""
