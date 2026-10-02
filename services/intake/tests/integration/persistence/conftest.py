import pytest


@pytest.fixture
def conn(test_db):
    """An autocommit connection: each statement is visible at once, as to a second connection."""
    with test_db.get_connection(autocommit=True) as connection:
        yield connection
