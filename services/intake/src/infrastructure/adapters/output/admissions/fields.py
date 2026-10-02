"""Strict readers for lead-core's JSON: each raises ValueError on a value of the wrong shape."""
from typing import Any
from uuid import UUID


def uuid_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("not a string")
    return str(UUID(value))


def integer(value: Any) -> int:
    # bool is an int subclass: `true` is not a score.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("not an integer")
    return value


def text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("not a string")
    return value
