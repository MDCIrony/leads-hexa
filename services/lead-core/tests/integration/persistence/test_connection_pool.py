from chassis.persistence import RawSqlDatabase


def test_connections_are_reused_across_calls(test_db):
    """Two sequential borrows must return the same underlying backend process,
    which is the observable difference between a pool and connect-per-call."""
    with test_db.get_connection(autocommit=True) as conn:
        first_pid = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    with test_db.get_connection(autocommit=True) as conn:
        second_pid = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    assert first_pid == second_pid


def test_rows_come_back_as_dictionaries(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        row = conn.execute("SELECT 1 AS answer").fetchone()
    assert row["answer"] == 1


def test_close_is_safe_to_call_twice(dsn_of_test_db):
    database = RawSqlDatabase(dsn=dsn_of_test_db)
    database.close()
    database.close()
