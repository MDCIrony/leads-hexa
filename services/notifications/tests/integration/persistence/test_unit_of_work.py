from uuid import uuid4

import pytest

from domain.exceptions import DomainException


def test_a_null_in_a_required_column_surfaces_as_a_domain_error(uow_factory):
    with pytest.raises(DomainException) as raised:
        with uow_factory() as uow:
            uow.connection.execute(
                "INSERT INTO members (agent_id, tenant_id, role, is_active, version) VALUES (%s, %s, NULL, TRUE, 1)",
                (uuid4(), uuid4()),
            )

    assert raised.value.error_code == "MISSING_REQUIRED_FIELD"


def test_an_error_inside_the_block_rolls_everything_back(uow_factory):
    event_id = uuid4()
    with pytest.raises(RuntimeError):
        with uow_factory() as uow:
            uow.processed_events.mark("group-a", event_id)
            raise RuntimeError("boom")

    with uow_factory() as uow:
        assert uow.processed_events.mark("group-a", event_id) is True
