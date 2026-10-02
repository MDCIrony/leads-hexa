"""Reconciliation against a scripted lookup: report-only, exit code by outcome."""
import argparse
import io
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest

from application.ports.output.admissions import AdmissionLookupItem, AdmissionLookupPort, AdmissionUnavailable
from infrastructure.cli.promoted_records import PromotedRecord
from infrastructure.cli.reconcile import _since, main, reconcile

_SINCE = datetime(2026, 10, 1, tzinfo=timezone.utc)


class _Lookup(AdmissionLookupPort):
    """Answers what lead-core holds per record: `known` maps record id → (tenant id, lead id)."""

    def __init__(self, known: dict, error: Exception | None = None) -> None:
        self.known, self.error, self.calls = known, error, []

    def lookup(self, intake_record_ids):
        self.calls.append(list(intake_record_ids))
        if self.error:
            raise self.error
        return [AdmissionLookupItem(str(i), *map(str, self.known[i])) for i in intake_record_ids if i in self.known]


def _record() -> PromotedRecord:
    return PromotedRecord(uuid4(), uuid4(), uuid4())


def _agreeing(*records: PromotedRecord) -> dict:
    return {r.record_id: (r.tenant_id, r.lead_id) for r in records}


def _run(batches, lookup):
    out = io.StringIO()
    return reconcile(batches, lookup, _SINCE, out), out.getvalue().splitlines()


def test_no_differences_exits_zero_and_says_how_many_it_checked():
    batches = [[_record(), _record()], [_record()]]
    lookup = _Lookup(_agreeing(*(r for batch in batches for r in batch)))

    code, lines = _run(batches, lookup)

    assert code == 0
    assert lines == [f"Reconciled 3 PROMOTED records since {_SINCE.isoformat()}: 0 differences"]
    assert [len(call) for call in lookup.calls] == [2, 1]


def test_each_kind_of_difference_is_named():
    missing, other_lead, other_tenant, fine = _record(), _record(), _record(), _record()
    lead, tenant = uuid4(), uuid4()
    lookup = _Lookup({**_agreeing(fine), other_lead.record_id: (other_lead.tenant_id, lead),
                      other_tenant.record_id: (tenant, other_tenant.lead_id)})

    code, lines = _run([[missing, other_lead, other_tenant, fine]], lookup)

    assert code == 1
    assert lines == [
        f"MISSING record={missing.record_id} tenant={missing.tenant_id} lead={missing.lead_id}",
        f"LEAD_MISMATCH record={other_lead.record_id} tenant={other_lead.tenant_id} "
        f"intake_lead={other_lead.lead_id} lead_core_lead={lead}",
        f"TENANT_MISMATCH record={other_tenant.record_id} tenant={other_tenant.tenant_id} lead_core_tenant={tenant}",
        f"Reconciled 4 PROMOTED records since {_SINCE.isoformat()}: 3 differences",
    ]


def test_lead_core_unavailable_is_neither_a_pass_nor_a_difference():
    code, lines = _run([[_record()]], _Lookup({}, AdmissionUnavailable("down")))

    assert code == 2 and lines == []


def test_intake_db_unreachable_is_no_answer_either():
    def batches():
        raise psycopg.OperationalError("connection refused")
        yield

    code, lines = _run(batches(), _Lookup({}))

    assert code == 2 and lines == []


def test_missing_configuration_is_no_answer(monkeypatch, capsys):
    monkeypatch.delenv("LEAD_CORE_URL", raising=False)

    assert main([]) == 2
    assert "LEAD_CORE_URL" in capsys.readouterr().err


def test_since_reads_a_naive_timestamp_as_utc():
    assert _since("2026-10-01T00:00:00") == _SINCE
    assert _since("2026-10-01T02:00:00+02:00") == _SINCE


def test_since_rejects_what_is_not_iso_8601():
    with pytest.raises(argparse.ArgumentTypeError):
        _since("yesterday")
