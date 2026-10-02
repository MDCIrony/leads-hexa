"""Compares intake's PROMOTED records with the admissions lead-core holds.

    python -m infrastructure.cli.reconcile [--since ISO8601]

Report-only: it never writes. A difference is repaired by admitting the record
again, which lead-core makes idempotent, not by touching another service's data.
Exits 1 if it found any difference, 2 if lead-core could not answer, 0 otherwise."""
import argparse
import logging
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import TextIO

from application.ports.output.admissions import AdmissionLookupPort, AdmissionUnavailable
from infrastructure.cli.promoted_records import PromotedRecord, promoted_since
from infrastructure.config.settings import WorkerSettings
from infrastructure.di.container import Container

# lead-core answers 422 above this many ids per lookup.
_BATCH_SIZE = 200
_DEFAULT_WINDOW = timedelta(hours=24)


def _differences(batch: list[PromotedRecord], lookup: AdmissionLookupPort) -> list[str]:
    known = {item.intake_record_id: item.lead_id for item in lookup.lookup([r.record_id for r in batch])}
    lines = []
    for record in batch:
        lead_core_lead = known.get(str(record.record_id))
        if lead_core_lead is None:
            lines.append(f"MISSING record={record.record_id} tenant={record.tenant_id} lead={record.lead_id}")
        elif lead_core_lead != str(record.lead_id):
            lines.append(f"LEAD_MISMATCH record={record.record_id} tenant={record.tenant_id} "
                         f"intake_lead={record.lead_id} lead_core_lead={lead_core_lead}")
    return lines


def reconcile(batches: Iterable[list[PromotedRecord]], lookup: AdmissionLookupPort, since: datetime,
              out: TextIO) -> int:
    checked = differences = 0
    try:
        for batch in batches:
            checked += len(batch)
            for line in _differences(batch, lookup):
                differences += 1
                print(line, file=out)
    except AdmissionUnavailable as exc:
        # No answer is not "no differences": a silent 0 would pass the exit criterion.
        print(f"lead-core unavailable after {checked} records: {exc}", file=sys.stderr)
        return 2
    print(f"Reconciled {checked} PROMOTED records since {since.isoformat()}: {differences} differences", file=out)
    return 1 if differences else 0


def _since(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO 8601 timestamp: {value!r}") from None
    # A naive value is read as UTC, the zone every timestamp in intake_db is stored in.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m infrastructure.cli.reconcile", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--since", type=_since, default=None, help="ISO 8601; defaults to 24 hours ago")
    args = parser.parse_args(argv)
    since = args.since or datetime.now(timezone.utc) - _DEFAULT_WINDOW
    # Logs to stderr, so stdout holds only the report.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    container = Container(WorkerSettings.from_environment())
    try:
        return reconcile(promoted_since(container.database, since, _BATCH_SIZE), container.admission_lookup,
                         since, sys.stdout)
    finally:
        container.close()


if __name__ == "__main__":
    sys.exit(main())
