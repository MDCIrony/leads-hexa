"""Static enforcement of the hexagonal dependency rule.

Reads each module's import statements from its syntax tree instead of importing
it, so a violation is reported even when the offending module cannot be
imported without its dependencies present."""

import ast
from pathlib import Path

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
    "httpx",
    "pandas",
    "numpy",
    "openpyxl",
}

_WEB_FRAMEWORKS_FORBIDDEN_IN_APPLICATION = {
    "fastapi",
    "starlette",
    "pydantic",
    "psycopg",
    "httpx",
    "pandas",
}


def _python_files(layer: str) -> list[Path]:
    return sorted((_SRC / layer).rglob("*.py"))


def _imported_roots(path: Path) -> set[str]:
    """Return the first segment of every module imported by this file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level > 0) stay inside the layer by definition.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _violations(layer: str, forbidden: set[str]) -> list[str]:
    found = []
    for path in _python_files(layer):
        offending = _imported_roots(path) & forbidden
        for module in sorted(offending):
            found.append(f"{path.relative_to(_SRC)} imports {module}")
    return found


def test_domain_does_not_import_outer_layers():
    violations = _violations("domain", {"application", "infrastructure"})
    assert violations == [], "Domain must not depend on outer layers:\n" + "\n".join(violations)


def test_application_does_not_import_infrastructure():
    violations = _violations("application", {"infrastructure"})
    assert violations == [], "Application must not depend on infrastructure:\n" + "\n".join(violations)


def test_domain_does_not_import_third_party_frameworks():
    violations = _violations("domain", _THIRD_PARTY_FORBIDDEN_IN_DOMAIN)
    assert violations == [], "Domain must depend only on the standard library:\n" + "\n".join(violations)


def test_application_does_not_import_web_frameworks():
    violations = _violations("application", _WEB_FRAMEWORKS_FORBIDDEN_IN_APPLICATION)
    assert violations == [], "Application must not depend on frameworks:\n" + "\n".join(violations)
