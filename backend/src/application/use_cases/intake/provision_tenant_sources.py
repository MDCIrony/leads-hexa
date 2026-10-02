from application.ports.input.intake.provision_tenant_sources_port import ProvisionTenantSourcesInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.intake.default_sources import DEFAULT_SOURCES, default_sources
from domain.value_objects.tenant_id import TenantId


class ProvisionTenantSourcesUseCase(ProvisionTenantSourcesInputPort):
    """Gives each new organization its default sources, once in its lifetime.

    The mark, not the sources, is what is checked: re-reading the compacted
    tenants topic must not recreate a source a manager deleted afterwards."""

    def apply(self, payload: dict, uow: UnitOfWorkPort) -> bool:
        tenant_id = TenantId(payload["tenant_id"])
        if not uow.provisioned_tenants.mark(tenant_id.value):
            return False
        # Marked anyway: a later reactivation is not a birth, and the topic
        # replay must stay a no-op for this tenant either way.
        if not payload["is_active"]:
            return False
        # Until the cut, CreateTenantUseCase still creates these sources for a
        # tenant born in the monolith, and only the migration seeded the marks.
        # Finding any of them means it is already provisioned.
        if any(uow.sources.get_by_kind(tenant_id.value, kind) for _, kind in DEFAULT_SOURCES):
            return False
        for source in default_sources(tenant_id):
            uow.sources.save(source)
        return True
