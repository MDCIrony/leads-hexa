from infrastructure.config.settings import Settings
from infrastructure.di.container import Container

_SETTINGS = Settings(database_url="postgresql://u:p@host:5432/db", jwt_secret="a-secret")


def test_stateless_adapters_are_shared_across_the_container_lifetime():
    """A fresh instance on every access would still be correct today (the
    assignment engine keeps no state of its own), but every other adapter
    listed here is shared for real reasons, so the container keeps treating
    all of them the same way."""
    container = Container(_SETTINGS)

    assert container.assignment_engine is container.assignment_engine
    assert container.password_hasher is container.password_hasher
    assert container.token_service is container.token_service
    assert container.event_publisher is container.event_publisher


def test_unit_of_work_is_built_fresh_on_every_call():
    """A unit of work owns one transaction; sharing it across requests would
    leak state between unrelated callers."""
    container = Container(_SETTINGS)

    assert container.unit_of_work() is not container.unit_of_work()
