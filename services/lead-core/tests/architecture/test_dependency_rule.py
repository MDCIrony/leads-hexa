"""Static enforcement of the hexagonal dependency rule, read from the syntax tree."""
from pathlib import Path

from chassis.testing import layer_violations, stdlib_only_violations

_SRC = Path(__file__).resolve().parents[2] / "src"


def test_domain_does_not_import_outer_layers():
    violations = layer_violations(_SRC, "domain", {"application", "infrastructure"})
    assert violations == [], "Domain must not depend on outer layers:\n" + "\n".join(violations)


def test_application_does_not_import_infrastructure():
    violations = layer_violations(_SRC, "application", {"infrastructure"})
    assert violations == [], "Application must not depend on infrastructure:\n" + "\n".join(violations)


def test_domain_imports_only_the_standard_library():
    violations = stdlib_only_violations(_SRC, "domain", {"domain"})
    assert violations == [], "Domain must depend only on the standard library:\n" + "\n".join(violations)


def test_application_imports_only_the_standard_library_and_the_domain():
    # chassis counts as infrastructure, so this also keeps it out of the application.
    violations = stdlib_only_violations(_SRC, "application", {"domain", "application"})
    assert violations == [], "Application must reach infrastructure through ports:\n" + "\n".join(violations)
