import os
from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class RawSqlDatabase:
    """Owns a pool of PostgreSQL connections.

    No silent fallback to another database: that is exactly what let this app
    run for a while writing to an unrelated in-memory SQLite instance while a
    real Postgres container sat empty next to it."""

    def __init__(self, dsn: Optional[str] = None, min_size: int = 1, max_size: int = 10) -> None:
        self.dsn = dsn or os.environ["DATABASE_URL"]
        self._min_size = min_size
        self._max_size = max_size
        # Opened lazily on first use rather than here: constructing this
        # object (e.g. the DI container in unit tests wired with a throwaway
        # DSN) must not spawn background connection-retry threads against a
        # host nothing ever intends to reach. ConnectionPool(open=True) does
        # not block on connect, but an unreachable pool left open still costs
        # a multi-second stall in its worker-thread shutdown at process exit.
        self._pool: Optional[ConnectionPool] = None

    def _get_pool(self) -> ConnectionPool:
        if self._pool is None:
            pool = ConnectionPool(
                conninfo=self.dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                kwargs={"row_factory": dict_row},
                open=True,
            )
            # open=True starts filling the pool in a background worker but
            # does not wait for it; without this, a borrow made immediately
            # after construction can race that worker and open a second
            # connection instead of reusing the one being established.
            pool.wait()
            self._pool = pool
        return self._pool

    @contextmanager
    def get_connection(self, autocommit: bool = False) -> Iterator[psycopg.Connection]:
        with self._get_pool().connection() as conn:
            conn.autocommit = autocommit
            yield conn

    def init_db(self) -> None:
        """Kept as the single entry point used by tests; the schema itself now
        lives in versioned .sql files."""
        from pathlib import Path

        from infrastructure.adapters.output.persistence.migration_runner import MigrationRunner

        migrations_dir = Path(__file__).resolve().parents[5] / "migrations"
        MigrationRunner(self, migrations_dir).apply_pending()

    def close(self) -> None:
        if self._pool is not None and not self._pool.closed:
            self._pool.close()
