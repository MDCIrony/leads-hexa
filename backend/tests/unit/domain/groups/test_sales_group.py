import uuid

import pytest

from domain.groups.sales_group import SalesGroup
from domain.exceptions import DomainException
from domain.value_objects.enums import AssignmentStrategy

_TENANT = uuid.uuid4()


class TestSalesGroupCreation:
    def test_a_group_belongs_to_one_organization(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas Norte")
        assert group.tenant_id.value == _TENANT
        assert group.name == "Ventas Norte"

    def test_the_default_strategy_is_lowest_load(self):
        """Spreading work evenly is the sane default; rotation is a choice."""
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        assert group.default_strategy == AssignmentStrategy.LOWEST_LOAD

    def test_a_group_is_active_and_uncapped_by_default(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        assert group.is_active is True
        assert group.capacity_per_agent is None

    def test_an_empty_name_is_rejected(self):
        with pytest.raises(DomainException) as exc:
            SalesGroup.create(tenant_id=_TENANT, name="   ")
        assert exc.value.error_code == "INVALID_GROUP_NAME"

    @pytest.mark.parametrize("capacity", [0, -1])
    def test_a_non_positive_capacity_is_rejected(self, capacity: int):
        """A capacity of zero would make the group unusable rather than uncapped;
        the way to say uncapped is None."""
        with pytest.raises(DomainException) as exc:
            SalesGroup.create(tenant_id=_TENANT, name="Ventas", capacity_per_agent=capacity)
        assert exc.value.error_code == "INVALID_GROUP_CAPACITY"

    def test_the_strategy_can_be_given_as_a_string(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas", default_strategy="ROUND_ROBIN")
        assert group.default_strategy == AssignmentStrategy.ROUND_ROBIN


class TestSalesGroupBehaviour:
    def test_deactivating_and_activating(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        group.deactivate()
        assert group.is_active is False
        group.activate()
        assert group.is_active is True

    def test_renaming_rejects_an_empty_name(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        with pytest.raises(DomainException):
            group.rename("")

    def test_an_uncapped_group_always_has_capacity(self):
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas")
        assert group.has_capacity_for(9999) is True

    def test_a_capped_group_excludes_an_agent_at_the_limit(self):
        """At the limit, not past it: capacity 5 means five is already full."""
        group = SalesGroup.create(tenant_id=_TENANT, name="Ventas", capacity_per_agent=5)
        assert group.has_capacity_for(4) is True
        assert group.has_capacity_for(5) is False
        assert group.has_capacity_for(6) is False
