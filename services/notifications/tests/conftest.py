import os
from pathlib import Path

import pytest

_MARKER_BY_DIRECTORY = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
    "architecture": "architecture",
}

_TESTS_ROOT = Path(__file__).parent

_DEFAULT_TEST_DSN = "postgresql://notifications_svc:notificationspassword@localhost:5433/notifications_test"

# Set at import time, once for the whole suite: conftest is imported before any
# test module, so a module that imports the app already finds them in place.
os.environ.setdefault("DATABASE_URL", os.getenv("TEST_DATABASE_URL", _DEFAULT_TEST_DSN))
os.environ.setdefault("JWKS_URL", "http://jwks.invalid/internal/v1/jwks")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")


def pytest_collection_modifyitems(items):
    """Derive the marker from the test's directory so that adding a file to
    tests/unit/ cannot silently escape `pytest -m unit`."""
    for item in items:
        relative = Path(item.fspath).relative_to(_TESTS_ROOT)
        marker = _MARKER_BY_DIRECTORY.get(relative.parts[0])
        if marker:
            item.add_marker(getattr(pytest.mark, marker))
