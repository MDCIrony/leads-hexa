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

_DEFAULT_TEST_DSN = "postgresql://lead_core_svc:leadcorepassword@localhost:5433/leads_test"

# Truncating this one would make the runner reapply every migration on the next
# test that touches the database.
_MIGRATIONS_TABLE = "schema_migrations"


def _test_dsn() -> str:
    return os.getenv("TEST_DATABASE_URL", _DEFAULT_TEST_DSN)


# Set at import time rather than in a fixture: `infrastructure.main` builds
# its settings from the environment, so an e2e module that imports the app needs these
# already present when its own import statement runs. conftest is imported
# before any test module, so one copy here covers every test — each e2e file
# used to carry its own, which meant a file without one passed only when
# another had already been imported first.
os.environ.setdefault("DATABASE_URL", _test_dsn())
# Never fetched: the e2e fixture below hands the app's Container the test keys.
os.environ.setdefault("JWKS_URL", "http://jwks.invalid/internal/v1/jwks")
os.environ.setdefault("SERVICE_CLIENT_SECRET", "test-service-secret-do-not-use")


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
    database = RawSqlDatabase(_test_dsn())
    MigrationRunner(database, _TESTS_ROOT.parent / "migrations").apply_pending()
    yield database
    database.close()


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


@pytest.fixture(autouse=True)
def identity_double(request, monkeypatch):
    """No identity runs next to the e2e suite: the Container the app builds
    verifies bearers against the test keys and asks an in-memory identity,
    through the same ports."""
    from tests.advisors_sync import IDENTITY

    IDENTITY.clear()
    if "e2e" not in request.node.keywords:
        return
    from functools import partial

    from infrastructure.di.container import Container
    from tests.advisors_sync import IdentityDouble
    from tests.tokens import jwks

    monkeypatch.setattr("infrastructure.di.container.HttpIdentityAgents", IdentityDouble)
    monkeypatch.setattr("infrastructure.main.Container", partial(Container, jwks_fetch=jwks))


@pytest.fixture
def dsn_of_test_db() -> str:
    return _test_dsn()
