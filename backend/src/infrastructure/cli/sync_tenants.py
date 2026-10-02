"""Backfills the tenants table for databases that predate it.

Organization identifiers used to circulate with no row backing them. This
creates one organization per distinct identifier still referenced by an agent,
so the data becomes consistent without discarding it. Run by hand, never at
startup: it is a one-off repair, not part of the boot sequence."""

from typing import List

from domain.entities.tenant import Tenant
from domain.events.identity_events import TenantState


def sync_tenants(uow) -> List[str]:
    created: List[str] = []
    with uow:
        rows = uow.agents.distinct_tenant_ids()
        for tenant_id in rows:
            if uow.tenants.get_by_id(tenant_id) is not None:
                continue
            short = str(tenant_id)[:8]
            # The identifier is preserved: existing agents already reference it.
            tenant = uow.tenants.save(
                Tenant.create(name=f"Organización {short}", tenant_id=tenant_id)
            )
            uow.outbox.record(TenantState.of(tenant), channel="internal")
            created.append(short)
    return created


if __name__ == "__main__":
    from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from infrastructure.config.settings import Settings

    settings = Settings.from_environment()
    database = RawSqlDatabase(dsn=settings.database_url)
    for slug in sync_tenants(PostgresUnitOfWork(database)):
        print(f"created organization for {slug}")
    database.close()
