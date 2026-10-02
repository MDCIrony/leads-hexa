import io
from typing import Any, List
from uuid import UUID

import pandas as pd

from application.dtos.reception import IngestLeadCommand
from application.ports.output.parsing import FileParserPort

KNOWN_FIELDS = {"first_name", "last_name", "email", "company", "budget", "industry", "phone"}


def _text(value: Any) -> str:
    """Blank, not the string "nan".

    pandas reads an empty text cell as NaN, and `str(NaN)` is the three-letter
    word "nan": it reached the customer as a company name, and made an
    IS_EMPTY condition false on a field that is empty."""
    return "" if value is None or pd.isna(value) else str(value).strip()


def _optional_text(value: Any) -> Any:
    """Same, except that absent means absent: email and phone are nullable, and
    a blank cell must not become an empty string a uniqueness check would see."""
    text = _text(value)
    return text or None


def _budget(value: Any) -> Any:
    """The cell as it arrived when it is not a number, so the domain rejects
    that one row into the tray with the field named.

    Raising here loses far more than the row: ProcessBatchUseCase reads any
    parse failure as an unreadable file, marks the job FAILED and records
    nothing at all — one cell reading "por determinar" used to take every
    good row of the file with it, unrecoverably."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


class PandasFileParser(FileParserPort):
    def parse_leads_file(
        self, file_content: bytes, filename: str, tenant_id: UUID, source_id: UUID
    ) -> List[IngestLeadCommand]:
        buffer = io.BytesIO(file_content)
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(buffer)
        else:
            df = pd.read_csv(buffer)

        df.columns = [str(column).strip().lower().replace(" ", "_") for column in df.columns]

        commands = []
        for _, row in df.iterrows():
            values = row.to_dict()
            commands.append(
                IngestLeadCommand(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    first_name=_text(values.get("first_name")),
                    last_name=_text(values.get("last_name")),
                    email=_optional_text(values.get("email")),
                    company=_text(values.get("company")),
                    budget=_budget(values.get("budget", 0)),
                    industry=_text(values.get("industry")),
                    custom_attributes={
                        key: value
                        for key, value in values.items()
                        if key not in KNOWN_FIELDS and pd.notna(value)
                    },
                    phone=_optional_text(values.get("phone")),
                )
            )

        return commands
