import threading
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

    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10) -> None:
        self.dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        # Opened lazily on first use rather than here: constructing this
        # object (e.g. the DI container in unit tests wired with a throwaway
        # DSN) must not spawn background connection-retry threads against a
        # host nothing ever intends to reach. ConnectionPool(open=True) does
        # not block on connect, but an unreachable pool left open still costs
        # a multi-second stall in its worker-thread shutdown at process exit.
        self._pool: Optional[ConnectionPool] = None
        # A worker's lanes reach the database for the first time together.
        self._pool_lock = threading.Lock()

    def _get_pool(self) -> ConnectionPool:
        if self._pool is not None:
            return self._pool
        with self._pool_lock:
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
                try:
                    pool.wait()
                except Exception:
                    # A consumer holding a message retries first use while the
                    # database is down; each failed pool would otherwise keep
                    # its connection threads alive.
                    pool.close()
                    raise
                self._pool = pool
        return self._pool

    @contextmanager
    def get_connection(self, autocommit: bool = False) -> Iterator[psycopg.Connection]:
        with self._get_pool().connection() as conn:
            conn.autocommit = autocommit
            yield conn

    def close(self) -> None:
        if self._pool is not None and not self._pool.closed:
            self._pool.close()
