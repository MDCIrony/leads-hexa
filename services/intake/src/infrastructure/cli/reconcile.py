"""Compares intake's PROMOTED records with the admissions lead-core holds.

    python -m infrastructure.cli.reconcile [--since ISO8601]

Report-only: it never writes. A difference is repaired by admitting the record
again, which lead-core makes idempotent, not by touching another service's data.
Exits 1 if it found any difference, 2 if it could not get an answer (missing
configuration, intake_db or lead-core unreachable), 0 otherwise."""
import argparse
import logging
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import TextIO

import psycopg

from application.ports.output.admissions import AdmissionLookupPort, AdmissionUnavailable
from infrastructure.cli.promoted_records import PromotedRecord, promoted_since
from infrastructure.config.settings import ReconcileSettings
from infrastructure.di.container import Container

# lead-core answers 422 above this many ids per lookup.
_BATCH_SIZE = 200
_DEFAULT_WINDOW = timedelta(hours=24)
_NO_ANSWER = 2


def _differences(batch: list[PromotedRecord], lookup: AdmissionLookupPort) -> list[str]:
    known = {item.intake_record_id: item for item in lookup.lookup([r.record_id for r in batch])}
    lines = []
    for record in batch:
        where = f"record={record.record_id} tenant={record.tenant_id}"
        item = known.get(str(record.record_id))
        if item is None:
            lines.append(f"MISSING {where} lead={record.lead_id}")
            continue
        if item.tenant_id != str(record.tenant_id):
            lines.append(f"TENANT_MISMATCH {where} lead_core_tenant={item.tenant_id}")
        if item.lead_id != str(record.lead_id):
            lines.append(f"LEAD_MISMATCH {where} intake_lead={record.lead_id} lead_core_lead={item.lead_id}")
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
    # No answer is not "no differences": a silent 0 would pass the exit criterion.
    except AdmissionUnavailable as exc:
        print(f"lead-core unavailable after {checked} records: {exc}", file=sys.stderr)
        return _NO_ANSWER
    except psycopg.Error as exc:
        print(f"intake_db unavailable after {checked} records: {exc!r}", file=sys.stderr)
        return _NO_ANSWER
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
    try:
        settings = ReconcileSettings.from_environment()
    except ValueError as exc:
        print(f"configuration incomplete: {exc}", file=sys.stderr)
        return _NO_ANSWER
    container = Container(settings)
    try:
        return reconcile(promoted_since(container.database, since, _BATCH_SIZE), container.admission_lookup,
                         since, sys.stdout)
    finally:
        container.close()


if __name__ == "__main__":
    sys.exit(main())
