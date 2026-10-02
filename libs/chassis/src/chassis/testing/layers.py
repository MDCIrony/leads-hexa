"""Layer guardian: reads imports from the syntax tree, so it reports a violation even when the
offending module cannot be imported."""
import sys
from pathlib import Path
from typing import Iterable

from chassis.testing.isolation import _import_nodes


def imported_roots(path) -> set[str]:
    """First segment of every absolute import of a file; relative ones stay inside the layer."""
    return {module.split(".")[0] for module, level in _import_nodes(path) if level == 0 and module}


def _violations(src_root, layer: str, offends) -> list[str]:
    src_root = Path(src_root)
    found = []
    for path in sorted((src_root / layer).rglob("*.py")):
        found.extend(f"{path.relative_to(src_root)} imports {root}"
                     for root in sorted(imported_roots(path)) if offends(root))
    return found


def layer_violations(src_root, layer: str, forbidden: Iterable[str]) -> list[str]:
    """'<path relative to src_root> imports <root>' for each file under src_root/layer that imports a forbidden root."""
    forbidden = set(forbidden)
    return _violations(src_root, layer, lambda root: root in forbidden)


def stdlib_only_violations(src_root, layer: str, allowed: Iterable[str]) -> list[str]:
    """Same shape, for every import whose root is neither in sys.stdlib_module_names nor in `allowed`."""
    permitted = {*allowed, *sys.stdlib_module_names}
    return _violations(src_root, layer, lambda root: root not in permitted)
