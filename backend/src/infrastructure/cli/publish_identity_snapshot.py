"""Republishes the current state of every agent and organization to the internal channel.

Run by hand to seed a consumer that starts from nothing, or to repair one that
missed a message. Safe to repeat: the snapshot carries each row's current
version and a projection drops what it already holds."""

from typing import Callable

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.events.identity_events import AgentState, TenantState


def publish_identity_snapshot(
    uow_factory: Callable[[], UnitOfWorkPort], page_size: int = 100,
) -> tuple[int, int]:
    """Returns how many (agents, tenants) were recorded."""
    # One transaction per page: a million-row table must not become one
    # transaction, and a crash midway leaves complete pages that a rerun repeats.
    agents = tenants = 0
    offset = 0
    while True:
        with uow_factory() as uow:
            page = uow.agents.list_all(limit=page_size, offset=offset)
            for agent in page:
                uow.outbox.record(AgentState.of(agent), channel="internal")
        agents += len(page)
        if len(page) < page_size:
            break
        offset += page_size

    offset = 0
    while True:
        with uow_factory() as uow:
            page = uow.tenants.list_all(limit=page_size, offset=offset)
            for tenant in page:
                uow.outbox.record(TenantState.of(tenant), channel="internal")
        tenants += len(page)
        if len(page) < page_size:
            break
        offset += page_size
    return agents, tenants


if __name__ == "__main__":
    from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from infrastructure.config.settings import Settings

    database = RawSqlDatabase(dsn=Settings.from_environment().database_url)
    recorded_agents, recorded_tenants = publish_identity_snapshot(lambda: PostgresUnitOfWork(database))
    print(f"recorded {recorded_agents} agent(s) and {recorded_tenants} organization(s)")
    database.close()
