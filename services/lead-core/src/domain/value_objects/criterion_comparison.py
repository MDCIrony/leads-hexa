from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Union

# Sentinel for "the lead has no such field", distinct from a field holding None.
MISSING = object()


def is_empty(actual: Any) -> bool:
    if actual is MISSING or actual is None:
        return True
    # A spreadsheet column left blank arrives as spaces. A rule that should
    # visibly match and does not is indistinguishable from a broken one.
    return isinstance(actual, str) and not actual.strip()


def equal(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    as_numbers = _as_decimals(actual, expected)
    if as_numbers is not None:
        return as_numbers[0] == as_numbers[1]
    return str(actual) == str(expected)


def compare(actual: Any, expected: Any, greater: bool) -> bool:
    as_numbers = _as_decimals(actual, expected)
    if as_numbers is None:
        return False
    left, right = as_numbers
    return left > right if greater else left < right


def in_options(actual: Any, options: Union[list, tuple]) -> bool:
    return any(equal(actual, option) for option in options)


def _as_decimals(left: Any, right: Any) -> Optional[tuple]:
    """Decimal, never float: money compared through binary floating point
    gives wrong answers for values a manager typed exactly."""
    try:
        return Decimal(str(left)), Decimal(str(right))
    except (InvalidOperation, ValueError, TypeError):
        return None
