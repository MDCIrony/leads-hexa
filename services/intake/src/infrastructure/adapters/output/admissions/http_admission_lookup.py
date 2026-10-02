from typing import Any
from uuid import UUID

from application.ports.output.admissions import AdmissionLookupItem, AdmissionLookupPort
from infrastructure.adapters.output.admissions.fields import uuid_text
from infrastructure.adapters.output.admissions.lead_core_client import LeadCoreClient, unavailable

# lead-core answers 422 above this many ids per call.
_BATCH_SIZE = 200


def _items(body: Any) -> list[AdmissionLookupItem]:
    return [
        AdmissionLookupItem(
            intake_record_id=uuid_text(item["intake_record_id"]),
            tenant_id=uuid_text(item["tenant_id"]),
            lead_id=uuid_text(item["lead_id"]),
        )
        for item in body["items"]
    ]


class HttpAdmissionLookup(AdmissionLookupPort):
    """`GET /internal/v1/admissions?intake_record_ids=...`, in batches."""

    def __init__(self, lead_core: LeadCoreClient) -> None:
        self._lead_core = lead_core

    def lookup(self, intake_record_ids: list[UUID]) -> list[AdmissionLookupItem]:
        found: list[AdmissionLookupItem] = []
        for start in range(0, len(intake_record_ids), _BATCH_SIZE):
            batch = intake_record_ids[start:start + _BATCH_SIZE]
            response = self._lead_core.send("GET", params=[("intake_record_ids", str(i)) for i in batch])
            try:
                found.extend(_items(response.json()))
            except (ValueError, KeyError, TypeError, AttributeError):
                raise unavailable("malformed lookup body") from None
        return found
