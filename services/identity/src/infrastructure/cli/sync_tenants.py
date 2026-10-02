"""Backfills the tenants table for databases that predate it.

Organization identifiers used to circulate with no row backing them. This
creates one organization per distinct identifier still referenced by an agent,
so the data becomes consistent without discarding it. Run by hand, never at
startup: it is a one-off repair, not part of the boot sequence."""

from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.events.identity_events import TenantState
from domain.tenants.tenant import Tenant


def sync_tenants(uow: UnitOfWorkPort) -> list[str]:
    created: list[str] = []
    with uow:
        for tenant_id in uow.agents.distinct_tenant_ids():
            if uow.tenants.get_by_id(tenant_id) is not None:
                continue
            short = str(tenant_id)[:8]
            # The identifier is preserved: existing agents already reference it.
            tenant = uow.tenants.save(Tenant.create(name=f"Organización {short}", tenant_id=tenant_id))
            uow.outbox.record(TenantState.of(tenant), channel="internal")
            created.append(short)
    return created


if __name__ == "__main__":
    from chassis.persistence import RawSqlDatabase

    from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork
    from infrastructure.cli.database_url import database_url

    database = RawSqlDatabase(database_url())
    for slug in sync_tenants(PostgresUnitOfWork(database)):
        print(f"created organization for {slug}")
    database.close()
