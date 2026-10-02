"""Legacy code over the structure limits (ADR-0037), with what each measured when the rule arrived.

Shrink-only: test_structure fails if an entry grows and also if it is left above
what the tree measures, so lowering or removing entries is part of the change
that shrinks the code. Each context leaves this list when it is extracted
(F3, F4, F5). Regenerate the values with `cd backend && uv run python -m chassis.testing measure src`."""

BASELINE = {
    "application/dtos/commands.py": 320,
    "application/ports/output/": 16,
    "application/use_cases/": 13,
    "application/use_cases/rule_use_cases.py": 193,
    "domain/entities/lead.py": 238,
    "domain/entities/rule.py": 229,
    "domain/value_objects/": 13,
    "domain/value_objects/criterion.py": 163,
    "infrastructure/adapters/input/api/dependencies.py": 282,
    "infrastructure/adapters/input/api/intake_router.py": 242,
    "infrastructure/adapters/input/api/lead_router.py": 228,
    "infrastructure/adapters/input/api/rule_router.py": 285,
    "infrastructure/adapters/input/api/schemas.py": 347,
    "infrastructure/adapters/output/persistence/": 16,
    "infrastructure/adapters/output/persistence/raw_sql_intake_record_repository.py": 170,
    "infrastructure/adapters/output/persistence/raw_sql_lead_repository.py": 246,
    "infrastructure/adapters/output/persistence/raw_sql_rule_repository.py": 177,
}
