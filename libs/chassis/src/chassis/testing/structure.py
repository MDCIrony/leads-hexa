"""Code structure rule (ADR-0037): lines per source file and .py files per folder."""
from pathlib import Path
from typing import Mapping

MAX_LINES = 150
MAX_FILES = 12


def measure(root, *, max_lines: int = MAX_LINES, max_files: int = MAX_FILES) -> dict[str, int]:
    """Everything under `root` over its limit, keyed by path relative to it.

    A file maps to its physical line count, blank lines and comments included.
    A folder, keyed with a trailing slash, maps to its own .py files other than
    `__init__.py`; subfolders are measured on their own."""
    root = Path(root)
    over: dict[str, int] = {}
    files_per_folder: dict[str, int] = {}
    for path in sorted(root.rglob("*.py")):
        # Bytes, not text: str.splitlines also breaks on form feeds and other
        # separators that no editor shows as a new line.
        lines = len(path.read_bytes().splitlines())
        if lines > max_lines:
            over[path.relative_to(root).as_posix()] = lines
        if path.name != "__init__.py":
            folder = path.parent.relative_to(root).as_posix() + "/"
            files_per_folder[folder] = files_per_folder.get(folder, 0) + 1
    over.update({folder: count for folder, count in files_per_folder.items() if count > max_files})
    return dict(sorted(over.items()))


def assert_structure(root, *, max_lines: int = MAX_LINES, max_files: int = MAX_FILES,
                     baseline: Mapping[str, int] = {}) -> None:
    """Fails unless every file and folder is within its limit or holds exactly its baseline value.

    The baseline only shrinks: growing an entry fails, and so does leaving one
    above what the tree now measures, because a recorded 300 lets a file that
    is down to 200 grow back unnoticed."""
    current = measure(root, max_lines=max_lines, max_files=max_files)
    problems = []
    for path, count in current.items():
        allowed = baseline.get(path)
        limit = max_files if path.endswith("/") else max_lines
        if allowed is None:
            problems.append(f"{path}: {count}, the limit is {limit}")
        elif count > allowed:
            problems.append(f"{path}: grew to {count}, its baseline is {allowed}")
        elif count < allowed:
            problems.append(f"{path}: shrank to {count}, lower its baseline to {count}")
    for path in sorted(baseline.keys() - current.keys()):
        problems.append(f"{path}: within the limit now, remove it from the baseline")
    assert not problems, "Code structure rule (ADR-0037) broken:\n" + "\n".join(problems)
