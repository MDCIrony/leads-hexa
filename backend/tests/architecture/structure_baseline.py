"""Legacy code over the structure limits (ADR-0037), with what each measured when the rule arrived.

Shrink-only: test_structure fails if an entry grows and also if it is left above
what the tree measures, so lowering or removing entries is part of the change
that shrinks the code. Each context leaves this list when it is extracted
(F5). Regenerate the values with `cd backend && uv run python -m chassis.testing measure src`."""

BASELINE = {
    "infrastructure/adapters/output/persistence/raw_sql_lead_repository.py": 238,
    "infrastructure/adapters/output/persistence/raw_sql_rule_repository.py": 177,
}
