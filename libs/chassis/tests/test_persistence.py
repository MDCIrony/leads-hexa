from contextlib import contextmanager

from chassis.persistence import MigrationRunner, RawSqlDatabase


class FakeConnection:
    def __init__(self, applied, log):
        self.applied, self.log = applied, log

    def execute(self, sql, params=None):
        self.log.append((sql.strip(), params))
        return self

    def fetchall(self):
        return [{"name": name} for name in self.applied]


class FakeDatabase:
    """Records the SQL the runner sends; `applied` pre-populates schema_migrations."""

    def __init__(self, applied=()):
        self.log, self.applied = [], applied

    @contextmanager
    def get_connection(self, autocommit=False):
        assert autocommit, "migrations must run outside a transaction"
        yield FakeConnection(self.applied, self.log)


def _migrations(tmp_path, *names):
    for name in names:
        (tmp_path / name).write_text(f"-- {name}", encoding="utf-8")
    return tmp_path


def _executed(database):
    return [sql for sql, _ in database.log]


def test_applies_pending_files_in_name_order(tmp_path):
    database = FakeDatabase()
    runner = MigrationRunner(database, _migrations(tmp_path, "002_b.sql", "001_a.sql", "010_c.sql"))

    assert runner.apply_pending() == ["001_a.sql", "002_b.sql", "010_c.sql"]
    assert [sql for sql in _executed(database) if sql.startswith("-- ")] == ["-- 001_a.sql", "-- 002_b.sql", "-- 010_c.sql"]
    recorded = [params for sql, params in database.log if sql.startswith("INSERT INTO schema_migrations")]
    assert recorded == [("001_a.sql",), ("002_b.sql",), ("010_c.sql",)]


def test_skips_migrations_already_recorded(tmp_path):
    database = FakeDatabase(applied=["001_a.sql"])
    runner = MigrationRunner(database, _migrations(tmp_path, "001_a.sql", "002_b.sql"))

    assert runner.apply_pending() == ["002_b.sql"]
    assert "-- 001_a.sql" not in _executed(database)


def test_ignores_files_that_are_not_sql(tmp_path):
    runner = MigrationRunner(FakeDatabase(), _migrations(tmp_path, "001_a.sql", "notes.txt"))

    assert runner.apply_pending() == ["001_a.sql"]


def test_constructing_the_database_does_not_open_the_pool():
    database = RawSqlDatabase("postgresql://nobody@unreachable.invalid:1/none")

    assert database._pool is None
    database.close()


def test_concurrent_first_use_builds_exactly_one_pool(monkeypatch):
    import threading
    import time

    from chassis.persistence import database as module

    built = []

    class SlowPool:
        def __init__(self, **kwargs):
            built.append(self)

        def wait(self):
            time.sleep(0.05)

    monkeypatch.setattr(module, "ConnectionPool", SlowPool)
    db = RawSqlDatabase("postgresql://unused")
    start = threading.Barrier(8)
    seen = []

    def first_use():
        start.wait()
        seen.append(db._get_pool())

    threads = [threading.Thread(target=first_use) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(built) == 1
    assert all(pool is built[0] for pool in seen)
