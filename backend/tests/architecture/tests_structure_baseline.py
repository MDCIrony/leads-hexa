"""Legacy test folders over the structure limit (ADR-0037), with what each held when the rule arrived.

Tests have no line limit, only the folder one. Shrink-only, like
structure_baseline.py: an entry that grows fails, and one left above what the
tree measures, or already within the limit, fails too. Regenerate with
`cd libs/chassis && uv run python -m chassis.testing measure ../../backend/tests --no-line-limit`."""

BASELINE = {
    "e2e/": 14,
    "unit/domain/": 13,
}
