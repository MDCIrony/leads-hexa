import io
import pandas as pd
from typing import List
from uuid import UUID
from application.ports.output.file_parser_port import FileParserPort
from application.dtos.commands import IngestLeadCommand

KNOWN_FIELDS = {"first_name", "last_name", "email", "company", "budget", "industry", "phone"}

class PandasFileParser(FileParserPort):
    def parse_leads_file(
        self, file_content: bytes, filename: str, tenant_id: UUID, source_id: UUID
    ) -> List[IngestLeadCommand]:
        buffer = io.BytesIO(file_content)
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(buffer)
        else:
            df = pd.read_csv(buffer)

        # Limpiar columnas
        df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

        commands = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            first_name = str(row_dict.get("first_name", "")).strip()
            last_name = str(row_dict.get("last_name", "")).strip()
            email = str(row_dict["email"]).strip() if "email" in row_dict and pd.notna(row_dict["email"]) else None
            if email == "":
                email = None
            company = str(row_dict.get("company", "")).strip()
            budget_val = float(row_dict.get("budget", 0))
            industry = str(row_dict.get("industry", "")).strip()
            phone = str(row_dict["phone"]).strip() if "phone" in row_dict and pd.notna(row_dict["phone"]) else None

            custom_attributes = {}
            for key, val in row_dict.items():
                if key not in KNOWN_FIELDS and pd.notna(val):
                    custom_attributes[key] = val

            commands.append(
                IngestLeadCommand(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    company=company,
                    budget=budget_val,
                    industry=industry,
                    custom_attributes=custom_attributes,
                    phone=phone,
                )
            )

        return commands
