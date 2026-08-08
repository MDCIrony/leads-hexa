import uuid
from typing import Any

import pytest

from domain.entities.lead_source import LeadSource
from domain.exceptions import DomainException
from domain.value_objects.enums import LeadSourceKind

_TENANT = uuid.uuid4()


def _source(**overrides: Any) -> LeadSource:
    base = dict(tenant_id=_TENANT, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
    base.update(overrides)
    return LeadSource.create(**base)


class TestCreate:
    def test_creates_with_the_given_fields(self):
        source = _source(name="Formulario web")
        assert source.name == "Formulario web"
        assert source.kind == LeadSourceKind.MANUAL_FORM
        assert source.tenant_id.value == _TENANT
        assert source.is_active is True
        assert source.field_mapping == {}

    def test_a_given_source_id_is_kept(self):
        fixed_id = uuid.uuid4()
        source = _source(source_id=fixed_id)
        assert source.id.value == fixed_id

    def test_an_empty_name_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _source(name="")
        assert exc.value.error_code == "SOURCE_WITHOUT_NAME"

    def test_a_whitespace_only_name_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _source(name="   ")
        assert exc.value.error_code == "SOURCE_WITHOUT_NAME"

    def test_the_name_is_trimmed(self):
        source = _source(name="  Formulario  ")
        assert source.name == "Formulario"

    def test_an_empty_mapping_key_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _source(field_mapping={"": "first_name"})
        assert exc.value.error_code == "INVALID_FIELD_MAPPING"

    def test_an_empty_mapping_value_is_refused(self):
        with pytest.raises(DomainException) as exc:
            _source(field_mapping={"nombre": ""})
        assert exc.value.error_code == "INVALID_FIELD_MAPPING"

    def test_a_valid_mapping_is_kept(self):
        source = _source(field_mapping={"nombre": "first_name"})
        assert source.field_mapping == {"nombre": "first_name"}


class TestRename:
    def test_renames_and_touches_updated_at(self):
        source = _source()
        before = source.updated_at
        source.rename("Nuevo nombre")
        assert source.name == "Nuevo nombre"
        assert source.updated_at >= before

    def test_renaming_to_empty_is_refused(self):
        source = _source()
        with pytest.raises(DomainException) as exc:
            source.rename("   ")
        assert exc.value.error_code == "SOURCE_WITHOUT_NAME"


class TestUpdateMapping:
    def test_replaces_the_mapping_and_touches_updated_at(self):
        source = _source()
        before = source.updated_at
        source.update_mapping({"correo": "email"})
        assert source.field_mapping == {"correo": "email"}
        assert source.updated_at >= before

    def test_an_invalid_mapping_is_refused(self):
        source = _source()
        with pytest.raises(DomainException) as exc:
            source.update_mapping({"correo": ""})
        assert exc.value.error_code == "INVALID_FIELD_MAPPING"


class TestDeactivate:
    def test_deactivates_and_touches_updated_at(self):
        source = _source()
        before = source.updated_at
        source.deactivate()
        assert source.is_active is False
        assert source.updated_at >= before
