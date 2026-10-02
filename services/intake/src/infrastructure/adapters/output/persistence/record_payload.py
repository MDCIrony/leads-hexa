import math
from typing import Any


def json_safe(value: Any) -> Any:
    """Replace what json.dumps would emit as a bare NaN/Infinity token.

    Postgres refuses those tokens as invalid JSONB, and a single one anywhere
    in the payload fails the whole insert, including the intake job it shares
    a transaction with. Recursive because custom_attributes is a free-form dict
    fed by untrusted input."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value
