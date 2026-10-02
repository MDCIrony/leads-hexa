"""Reconciliation against a scripted lookup: report-only, exit code by outcome."""
import io
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from application.ports.output.admissions import AdmissionLookupItem, AdmissionLookupPort, AdmissionUnavailable
from infrastructure.cli.promoted_records import PromotedRecord
from infrastructure.cli.reconcile import _since, reconcile

_SINCE = datetime(2026, 10, 1, tzinfo=timezone.utc)


class _Lookup(AdmissionLookupPort):
    def __init__(self, lead_by_record: dict, error: Exception | None = None) -> None:
        self.lead_by_record, self.error, self.calls = lead_by_record, error, []

    def lookup(self, intake_record_ids):
        self.calls.append(list(intake_record_ids))
        if self.error:
            raise self.error
        return [AdmissionLookupItem(str(i), str(uuid4()), self.lead_by_record[i])
                for i in intake_record_ids if i in self.lead_by_record]


def _record() -> PromotedRecord:
    return PromotedRecord(uuid4(), uuid4(), uuid4())


def _run(batches, lookup):
    out = io.StringIO()
    return reconcile(batches, lookup, _SINCE, out), out.getvalue().splitlines()


def test_no_differences_exits_zero_and_says_how_many_it_checked():
    batches = [[_record(), _record()], [_record()]]
    lookup = _Lookup({r.record_id: str(r.lead_id) for batch in batches for r in batch})

    code, lines = _run(batches, lookup)

    assert code == 0
    assert lines == [f"Reconciled 3 PROMOTED records since {_SINCE.isoformat()}: 0 differences"]
    assert [len(call) for call in lookup.calls] == [2, 1]


def test_a_record_lead_core_does_not_know_and_a_different_lead_are_each_named():
    missing, mismatched, fine = _record(), _record(), _record()
    other_lead = str(uuid4())
    lookup = _Lookup({mismatched.record_id: other_lead, fine.record_id: str(fine.lead_id)})

    code, lines = _run([[missing, mismatched, fine]], lookup)

    assert code == 1
    assert lines == [
        f"MISSING record={missing.record_id} tenant={missing.tenant_id} lead={missing.lead_id}",
        f"LEAD_MISMATCH record={mismatched.record_id} tenant={mismatched.tenant_id} "
        f"intake_lead={mismatched.lead_id} lead_core_lead={other_lead}",
        f"Reconciled 3 PROMOTED records since {_SINCE.isoformat()}: 2 differences",
    ]


def test_lead_core_unavailable_is_neither_a_pass_nor_a_difference():
    code, lines = _run([[_record()]], _Lookup({}, AdmissionUnavailable("down")))

    assert code == 2 and lines == []


def test_since_reads_a_naive_timestamp_as_utc():
    assert _since("2026-10-01T00:00:00") == _SINCE
    assert _since("2026-10-01T02:00:00+02:00") == _SINCE


def test_since_rejects_what_is_not_iso_8601():
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        _since("yesterday")
