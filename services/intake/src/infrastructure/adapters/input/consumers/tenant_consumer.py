from collections.abc import Callable

from chassis.consumer import Envelope

from application.ports.input.tenants import ProvisionTenantSourcesInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.tenants.provision_tenant_sources import ProvisionTenantSourcesUseCase


class TenantConsumer:
    """Provisions each new organization's default sources from the tenant state topic.

    Creating sources is not idempotent, so the processed mark shares the
    transaction with the effect: a failure undoes both and a duplicate finds
    the mark and does nothing."""

    def __init__(self, uow_factory: Callable[[], UnitOfWorkPort], group: str) -> None:
        self._uow_factory = uow_factory
        self._group = group
        self._provision: ProvisionTenantSourcesInputPort = ProvisionTenantSourcesUseCase()

    def __call__(self, envelope: Envelope) -> None:
        if envelope.event_type != "TenantState":
            return
        with self._uow_factory() as uow:
            if uow.processed_events.mark(self._group, envelope.event_id):
                self._provision.apply(envelope.payload, uow)
