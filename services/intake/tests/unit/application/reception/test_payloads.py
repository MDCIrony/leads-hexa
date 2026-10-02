import json
from decimal import Decimal
from uuid import uuid4

import pytest

from application.dtos.reception import IngestLeadCommand
from application.use_cases.reception.payloads import candidate_of, command_from_record, payload_of
from domain.records.intake_record import IntakeRecord


def _command(**fields) -> IngestLeadCommand:
    return IngestLeadCommand(tenant_id=uuid4(), source_id=uuid4(), **fields)


@pytest.mark.parametrize("budget", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_budget_is_stored_as_null_so_postgres_accepts_the_batch(budget):
    payload = payload_of(_command(first_name="Juan", budget=budget))

    assert payload["budget"] is None
    # allow_nan=False makes the assertion real: the default emits the bare NaN token Postgres refuses.
    json.dumps(payload, allow_nan=False)


def test_a_decimal_budget_is_stored_as_a_number():
    assert payload_of(_command(budget=Decimal("10.50")))["budget"] == 10.5


def test_the_stored_payload_rebuilds_a_command_whose_organization_comes_from_the_record():
    record = IntakeRecord.create(
        tenant_id=uuid4(), source_id=uuid4(),
        payload={"tenant_id": str(uuid4()), "source_id": str(uuid4()), "email": "a@b.co",
                 "custom_attributes": None},
    )

    command = command_from_record(record)

    assert (command.tenant_id, command.source_id) == (record.tenant_id.value, record.source_id.value)
    assert (command.email, command.custom_attributes, command.first_name) == ("a@b.co", {}, None)


@pytest.mark.parametrize("value, text", [
    (5000, "5000"),
    (1234.5, "1234.5"),
    (0.1, "0.1"),
    (5000.0, "5000.0"),
    ("12.30", "12.30"),
    (Decimal("7.25"), "7.25"),
    (None, None),
])
def test_budget_travels_as_text_without_binary_noise(value, text):
    assert candidate_of(_command(budget=value)).budget == text


def test_any_other_scalar_travels_as_text_and_nulls_stay_null():
    candidate = candidate_of(_command(phone=600123456, first_name="Ana", custom_attributes={"k": 1}))

    assert (candidate.phone, candidate.first_name, candidate.email) == ("600123456", "Ana", None)
    assert candidate.custom_attributes == {"k": 1}
