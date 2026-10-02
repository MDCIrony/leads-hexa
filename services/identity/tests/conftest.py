import os
from pathlib import Path

import pytest

from tests import environment

_MARKER_BY_DIRECTORY = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
    "architecture": "architecture",
}

_TESTS_ROOT = Path(__file__).parent

_DEFAULT_TEST_DSN = "postgresql://identity_svc:identitypassword@localhost:5433/identity_test"

# Truncating this one would make the runner reapply every migration on the next
# test that touches the database.
_MIGRATIONS_TABLE = "schema_migrations"

# Set at import time, once for the whole suite: conftest is imported before any
# test module, so a module that imports the app already finds them in place.
_TEST_DSN = os.getenv("TEST_DATABASE_URL", _DEFAULT_TEST_DSN)
os.environ.setdefault("DATABASE_URL", _TEST_DSN)
os.environ.setdefault("SIGNING_KEYS", environment.SIGNING_KEYS)
os.environ.setdefault("MFA_ENCRYPTION_KEY", environment.MFA_ENCRYPTION_KEY)
os.environ.setdefault("SERVICE_CLIENTS", environment.SERVICE_CLIENTS)


def pytest_collection_modifyitems(items):
    """Derive the marker from the test's directory so that adding a file to
    tests/unit/ cannot silently escape `pytest -m unit`."""
    for item in items:
        relative = Path(item.fspath).relative_to(_TESTS_ROOT)
        marker = _MARKER_BY_DIRECTORY.get(relative.parts[0])
        if marker:
            item.add_marker(getattr(pytest.mark, marker))


@pytest.fixture(scope="session")
def test_db():
    from chassis.persistence import MigrationRunner, RawSqlDatabase

    # The database itself is created by db-bootstrap: the service role has no CREATEDB.
    database = RawSqlDatabase(_TEST_DSN)
    MigrationRunner(database, _TESTS_ROOT.parent / "migrations").apply_pending()
    yield database
    database.close()


@pytest.fixture(autouse=True)
def clean_tables(request):
    """Truncate before each database-backed test.

    The table list comes from the catalog: a new table nobody adds to a
    hard-coded list would leak rows between tests. A wrapping rollback would
    not work, since the unit of work opens its own connection and commits."""
    if not set(request.node.keywords) & {"integration", "e2e"}:
        return

    from psycopg import sql

    database = request.getfixturevalue("test_db")
    with database.get_connection(autocommit=True) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> %s",
            (_MIGRATIONS_TABLE,),
        ).fetchall()
        if rows:
            conn.execute(
                sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(row["tablename"]) for row in rows)
                )
            )


@pytest.fixture
def uow_factory(test_db):
    from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork

    return lambda: PostgresUnitOfWork(test_db)
