"""Structure baselines (ADR-0037) of the repository roots that have no test suite of their own.

Read by scripts/verify-structure.sh. Shrink-only.
Regenerate an entry with `cd libs/chassis && uv run python -m chassis.testing measure ../../<root>`."""

TEST_CONSUMER = {
    "app.py": 551,
}
