import json
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class Envelope:
    event_id: UUID
    event_type: str
    schema_version: int
    occurred_at: str
    producer: str
    tenant_id: Optional[str]
    aggregate_id: str
    correlation_id: Optional[str]
    payload: dict

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Envelope":
        """Raises ValueError on anything that is not a well-formed envelope."""
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("envelope is not a JSON object")
            strings = {k: body[k] for k in ("event_type", "occurred_at", "producer", "aggregate_id")}
            optional = {k: body[k] for k in ("tenant_id", "correlation_id")}
            version, payload = body["schema_version"], body["payload"]
            if not all(isinstance(v, str) for v in strings.values()):
                raise ValueError("envelope string field has the wrong type")
            if not all(v is None or isinstance(v, str) for v in optional.values()):
                raise ValueError("envelope optional field has the wrong type")
            if isinstance(version, bool) or not isinstance(version, int):
                raise ValueError("schema_version is not an integer")
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            return cls(event_id=UUID(body["event_id"]), schema_version=version,
                       payload=payload, **strings, **optional)
        except (KeyError, TypeError, AttributeError, UnicodeDecodeError, RecursionError) as exc:
            # json.JSONDecodeError and the UUID error are already ValueErrors.
            # RecursionError: deeply nested input such as b"[" * 100000 would
            # otherwise escape, and a poison message would block its partition.
            raise ValueError(f"malformed envelope: {exc!r}") from exc
