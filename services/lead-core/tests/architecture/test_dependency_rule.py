"""Static enforcement of the hexagonal dependency rule.

Reads each module's import statements from its syntax tree instead of importing
it, so a violation is reported even when the offending module cannot be
imported without its dependencies present."""

from pathlib import Path

from chassis.testing import layer_violations

_SRC = Path(__file__).resolve().parents[2] / "src"

# Everything the domain is allowed to depend on beyond the standard library:
# nothing. Listed explicitly so that adding a dependency is a deliberate act.
_THIRD_PARTY_FORBIDDEN_IN_DOMAIN = {
    "pydantic",
    "fastapi",
    "starlette",
    "sqlalchemy",
    "psycopg",
    "passlib",
    "bcrypt",
    "jwt",
    "cryptography",
    "chassis",
    "httpx",
    "pandas",
    "numpy",
    "openpyxl",
    "confluent_kafka",
    "kafka",
    "pika",
    "aio_pika",
}

# Not just web frameworks: every concrete piece of infrastructure the
# application layer must reach through a port instead of importing. `chassis`
# is the shared service library and belongs to infrastructure only.
_INFRASTRUCTURE_FORBIDDEN_IN_APPLICATION = {
    "fastapi",
    "starlette",
    "pydantic",
    "psycopg",
    "httpx",
    "pandas",
    "jwt",
    "cryptography",
    "chassis",
    "confluent_kafka",
    "kafka",
    "pika",
    "aio_pika",
}


def test_domain_does_not_import_outer_layers():
    violations = layer_violations(_SRC, "domain", {"application", "infrastructure"})
    assert violations == [], "Domain must not depend on outer layers:\n" + "\n".join(violations)


def test_application_does_not_import_infrastructure():
    violations = layer_violations(_SRC, "application", {"infrastructure"})
    assert violations == [], "Application must not depend on infrastructure:\n" + "\n".join(violations)


def test_domain_does_not_import_third_party_frameworks():
    violations = layer_violations(_SRC, "domain", _THIRD_PARTY_FORBIDDEN_IN_DOMAIN)
    assert violations == [], "Domain must depend only on the standard library:\n" + "\n".join(violations)


def test_application_does_not_import_infrastructure_libraries():
    violations = layer_violations(_SRC, "application", _INFRASTRUCTURE_FORBIDDEN_IN_APPLICATION)
    assert violations == [], "Application must reach infrastructure through ports:\n" + "\n".join(violations)
