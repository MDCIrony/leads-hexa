"""Domain tests depend on the domain alone (ADR-0037)."""
import ast
import sys
from pathlib import Path


def imported_modules(path) -> set[str]:
    """Absolute module names a file imports, read from its syntax tree without importing it.

    Relative imports are left out: they stay inside the file's own package."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _lives_under(module: str, tests_root: Path) -> bool:
    """Whether `module` resolves to a file or package under `tests_root`, from any ancestor of it.

    The same helper is reachable as `helpers` or as `tests.unit.domain.helpers`
    depending on what is on the path, so every anchor is tried."""
    relative = Path(*module.split("."))
    for anchor in (tests_root, *tests_root.parents):
        candidate = anchor / relative
        if candidate.with_suffix(".py").is_file() or candidate.is_dir():
            return candidate.resolve().is_relative_to(tests_root)
    return False


def assert_domain_tests_isolated(tests_root, domain_package: str) -> None:
    """Fails if a test under `tests_root` imports anything but the domain, the stdlib, pytest
    or helpers that live under `tests_root` itself."""
    tests_root = Path(tests_root).resolve()
    allowed = {domain_package, "pytest", *sys.stdlib_module_names}
    problems = [
        f"{path.relative_to(tests_root)} imports {module}"
        for path in sorted(tests_root.rglob("*.py"))
        for module in sorted(imported_modules(path))
        if module.split(".")[0] not in allowed and not _lives_under(module, tests_root)
    ]
    assert not problems, "Domain tests must import only the domain:\n" + "\n".join(problems)
