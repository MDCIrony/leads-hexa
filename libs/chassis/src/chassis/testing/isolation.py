"""Domain tests depend on the domain alone (ADR-0037).

Imports are read from the syntax tree, so dynamic ones (`importlib.import_module`,
`__import__`) are not detected."""
import ast
import sys
from pathlib import Path


def _import_nodes(path) -> list[tuple[str, int]]:
    """(module, level) for every import statement; level > 0 is a relative import."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level))
    return found


def imported_modules(path) -> set[str]:
    """Absolute module names a file imports, read without importing it. Relative imports are left out."""
    return {module for module, level in _import_nodes(path) if level == 0 and module}


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


def _relative_target(path: Path, module: str, level: int) -> Path:
    base = path.parent
    for _ in range(level - 1):
        base = base.parent
    return base.joinpath(*module.split(".")) if module else base


def assert_domain_tests_isolated(tests_root, domain_package: str) -> None:
    """Fails if a test under `tests_root` imports anything but the domain, the stdlib, pytest
    or helpers that live under `tests_root` itself.

    A relative import is resolved against the file: one that climbs out of
    `tests_root` fails, since nothing the rule allows lives up there."""
    tests_root = Path(tests_root).resolve()
    allowed = {domain_package, "pytest", *sys.stdlib_module_names}
    problems = []
    for path in sorted(tests_root.rglob("*.py")):
        for module, level in sorted(set(_import_nodes(path))):
            if level:
                target = _relative_target(path, module, level)
                if not target.resolve().is_relative_to(tests_root):
                    problems.append(f"{path.relative_to(tests_root)} imports {'.' * level}{module}")
            elif module.split(".")[0] not in allowed and not _lives_under(module, tests_root):
                problems.append(f"{path.relative_to(tests_root)} imports {module}")
    assert not problems, "Domain tests must import only the domain:\n" + "\n".join(problems)
