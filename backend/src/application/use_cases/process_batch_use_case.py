import uuid
from uuid import UUID
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.output.file_parser_port import FileParserPort
from application.dtos.commands import BatchProcessResult

class ProcessBatchUseCase(ProcessBatchInputPort):
    def __init__(
        self,
        file_parser: FileParserPort,
        ingest_lead_use_case: IngestLeadInputPort,
    ) -> None:
        self.file_parser = file_parser
        self.ingest_lead_use_case = ingest_lead_use_case

    def execute(self, file_content: bytes, filename: str, tenant_id: UUID) -> BatchProcessResult:
        commands = self.file_parser.parse_leads_file(file_content, filename, tenant_id)
        results = []
        successful = 0
        failed_rows = []

        for idx, cmd in enumerate(commands, start=1):
            res = self.ingest_lead_use_case.execute(cmd)
            results.append(res)
            if res.error:
                failed_rows.append({"row_number": idx, "email": cmd.email, "error": res.error})
            else:
                successful += 1

        return BatchProcessResult(
            job_id=str(uuid.uuid4()),
            total_rows=len(commands),
            successful_ingestions=successful,
            failed_rows=failed_rows,
        )
