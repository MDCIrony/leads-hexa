"""Republishes the current state of every agent and organization to the internal channel.

Run by hand to seed a consumer that starts from nothing, or to repair one that
missed a message. Safe to repeat: the snapshot carries each row's current
version and a projection drops what it already holds."""

from collections.abc import Callable

from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.events.identity_events import AgentState, TenantState


def publish_identity_snapshot(
    uow_factory: Callable[[], UnitOfWorkPort], page_size: int = 100,
) -> tuple[int, int]:
    """Returns how many (agents, tenants) were recorded."""
    # One transaction per page: a million-row table must not become one
    # transaction, and a crash midway leaves complete pages that a rerun repeats.
    agents = _record_pages(uow_factory, page_size, lambda uow, **page: uow.agents.list_all(**page), AgentState)
    tenants = _record_pages(uow_factory, page_size, lambda uow, **page: uow.tenants.list_all(**page), TenantState)
    return agents, tenants


def _record_pages(uow_factory, page_size, list_page, state) -> int:
    recorded = offset = 0
    while True:
        with uow_factory() as uow:
            page = list_page(uow, limit=page_size, offset=offset)
            for entity in page:
                uow.outbox.record(state.of(entity), channel="internal")
        recorded += len(page)
        if len(page) < page_size:
            return recorded
        offset += page_size


if __name__ == "__main__":
    from chassis.persistence import RawSqlDatabase

    from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
    from infrastructure.cli.database_url import database_url

    database = RawSqlDatabase(database_url())
    recorded_agents, recorded_tenants = publish_identity_snapshot(lambda: PostgresUnitOfWork(database))
    print(f"recorded {recorded_agents} agent(s) and {recorded_tenants} organization(s)")
    database.close()
