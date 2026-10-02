#!/usr/bin/env bash
#
# Code structure rule (ADR-0037) over every Python root of the repository.
#
# Sources: at most 150 lines per file and 12 .py files per folder. Tests: the
# folder limit only. Legacy code is held to its shrink-only baseline. Runs on
# the chassis project's own environment: no Docker, no database.
#
#   ./scripts/verify-structure.sh
#
# A new Python root is added here, with its baseline if it starts over the limits.

set -u

REPO=$(cd "$(dirname "$0")/.." && pwd)
FAILURES=0

check() {
  (cd "$REPO/libs/chassis" && uv run --quiet python -m chassis.testing check "$@") || FAILURES=$((FAILURES + 1))
}

check "$REPO/backend/src"       --baseline "$REPO/backend/tests/architecture/structure_baseline.py"
check "$REPO/backend/tests"     --no-line-limit --baseline "$REPO/backend/tests/architecture/tests_structure_baseline.py"
check "$REPO/libs/chassis/src"
check "$REPO/libs/chassis/tests" --no-line-limit
check "$REPO/services/notifications/src"
check "$REPO/services/notifications/tests" --no-line-limit
check "$REPO/test-consumer"     --baseline "$REPO/scripts/structure_baseline.py:TEST_CONSUMER"
check "$REPO/demo"              --baseline "$REPO/scripts/structure_baseline.py:DEMO"
check "$REPO/tools"

if [ "$FAILURES" -gt 0 ]; then
  echo "$FAILURES root(s) break the structure rule." >&2
  exit 1
fi
echo "Structure rule: every root green."
