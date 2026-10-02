from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from domain.tenants.tenant import Tenant, slugify
from domain.exceptions import DomainException


class TestSlugify:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("Acme Corp", "acme-corp"),
            ("  Spaced  Out  ", "spaced-out"),
            ("ACME", "acme"),
            ("Ñandú & Cía.", "nandu-cia"),
            ("multi---dash", "multi-dash"),
            ("Solución 360", "solucion-360"),
        ],
    )
    def test_produces_a_url_safe_identifier(self, value: str, expected: str):
        assert slugify(value) == expected

    def test_rejects_a_value_with_no_usable_characters(self):
        with pytest.raises(DomainException):
            slugify("!!!")


class TestCreation:
    def test_derives_the_slug_from_the_name(self):
        assert Tenant.create(name="Acme Corp").slug == "acme-corp"

    def test_accepts_an_explicit_slug(self):
        assert Tenant.create(name="Acme Corp", slug="legacy-acme").slug == "legacy-acme"

    def test_generates_an_identifier_when_none_is_given(self):
        assert isinstance(Tenant.create(name="Acme").id.value, UUID)

    def test_accepts_an_explicit_identifier(self):
        given = uuid4()
        assert str(Tenant.create(name="Acme", tenant_id=given).id) == str(given)

    def test_is_active_by_default(self):
        assert Tenant.create(name="Acme").is_active is True

    def test_stamps_a_creation_time(self):
        moment = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
        assert Tenant.create(name="Acme", created_at=moment).created_at == moment

    def test_rejects_an_empty_name(self):
        with pytest.raises(DomainException):
            Tenant.create(name="")

    def test_rejects_a_whitespace_only_name(self):
        with pytest.raises(DomainException):
            Tenant.create(name="   ")

    def test_trims_the_name(self):
        assert Tenant.create(name="  Acme  ").name == "Acme"


class TestLifecycle:
    def test_deactivate_marks_it_inactive(self):
        tenant = Tenant.create(name="Acme")
        tenant.deactivate()
        assert tenant.is_active is False

    def test_activate_restores_it(self):
        tenant = Tenant.create(name="Acme")
        tenant.deactivate()
        tenant.activate()
        assert tenant.is_active is True

    def test_rename_changes_the_name(self):
        tenant = Tenant.create(name="Acme")
        tenant.rename("Acme Global")
        assert tenant.name == "Acme Global"

    def test_rename_does_not_change_the_slug(self):
        """The slug is a stable reference: renaming must not break anything
        that already points at this organization."""
        tenant = Tenant.create(name="Acme Corp")
        tenant.rename("Totally Different")
        assert tenant.slug == "acme-corp"

    def test_rename_rejects_an_empty_name(self):
        tenant = Tenant.create(name="Acme")
        with pytest.raises(DomainException):
            tenant.rename("  ")
