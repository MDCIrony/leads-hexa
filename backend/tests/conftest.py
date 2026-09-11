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

_DEFAULT_TEST_DSN = "postgresql://postgres:postgrespassword@localhost:5433/leads_test"

# Truncating this one would make the runner reapply every migration on the next
# test that touches the database.
_MIGRATIONS_TABLE = "schema_migrations"


def _test_dsn() -> str:
    return os.getenv("TEST_DATABASE_URL", _DEFAULT_TEST_DSN)


# Set at import time rather than in a fixture: `infrastructure.main` reads
# Settings at module level, so an e2e module that imports the app needs these
# already present when its own import statement runs. conftest is imported
# before any test module, so one copy here covers every test — each e2e file
# used to carry its own, which meant a file without one passed only when
# another had already been imported first.
os.environ.setdefault("DATABASE_URL", _test_dsn())
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("MFA_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")


def pytest_collection_modifyitems(items):
    """Derive the marker from the test's directory so that adding a file to
    tests/unit/ cannot silently escape `pytest -m unit`."""
    for item in items:
        relative = Path(item.fspath).relative_to(_TESTS_ROOT)
        marker = _MARKER_BY_DIRECTORY.get(relative.parts[0])
        if marker:
            item.add_marker(getattr(pytest.mark, marker))


def _ensure_test_database_exists(dsn: str) -> None:
    """Create the test database if it is missing, connecting to the maintenance
    database first. CREATE DATABASE cannot run inside a transaction."""
    import psycopg
    from urllib.parse import urlparse

    parsed = urlparse(dsn)
    database = parsed.path.lstrip("/")
    admin_dsn = dsn.replace(f"/{database}", "/postgres")

    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{database}"')


@pytest.fixture(scope="session")
def test_db():
    from infrastructure.adapters.output.persistence.connection import RawSqlDatabase

    dsn = _test_dsn()
    _ensure_test_database_exists(dsn)
    database = RawSqlDatabase(dsn=dsn)
    database.init_db()
    return database


@pytest.fixture(autouse=True)
def clean_tables(request):
    """Truncate before each database-backed test.

    The table list comes from the catalog instead of a literal: a new table
    nobody remembers to add to a hard-coded list leaks rows between tests, and
    nothing turns red until some unrelated test fails for reasons of its own.

    A wrapping transaction with rollback would not work here: the unit of work
    opens its own connection and commits on its own, so an outer rollback would
    never see those rows."""
    if not set(request.node.keywords) & {"integration", "e2e"}:
        return

    from psycopg import sql

    database = request.getfixturevalue("test_db")
    with database.get_connection(autocommit=True) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename <> %s",
            (_MIGRATIONS_TABLE,),
        ).fetchall()
        if not rows:
            return
        conn.execute(
            sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(sql.Identifier(row["tablename"]) for row in rows)
            )
        )


@pytest.fixture
def dsn_of_test_db() -> str:
    return _test_dsn()
