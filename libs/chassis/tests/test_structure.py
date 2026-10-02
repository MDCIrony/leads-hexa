import re
from pathlib import Path

import pytest

from chassis.testing import assert_domain_tests_isolated, assert_structure, measure
from chassis.testing.cli import main

_CHASSIS = Path(__file__).resolve().parents[1]


def test_chassis_follows_the_structure_rule_without_a_baseline():
    assert_structure(_CHASSIS / "src")
    assert_structure(_CHASSIS / "tests", max_lines=None)


def _write(path: Path, lines: int = 1, text: str = "x = 1") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([text] * lines) + "\n")
    return path


def test_a_file_at_the_limit_passes_and_one_line_more_fails(tmp_path):
    _write(tmp_path / "pkg" / "ok.py", 150)
    assert_structure(tmp_path)

    _write(tmp_path / "pkg" / "big.py", 151)
    with pytest.raises(AssertionError, match="pkg/big.py: 151, the limit is 150"):
        assert_structure(tmp_path)


def test_blank_lines_and_comments_count(tmp_path):
    _write(tmp_path / "a.py", 151, text="")
    _write(tmp_path / "b.py", 151, text="# why")
    assert measure(tmp_path) == {"a.py": 151, "b.py": 151}


def test_a_folder_counts_its_own_files_without_init_or_subfolders(tmp_path):
    for i in range(12):
        _write(tmp_path / "pkg" / f"m{i}.py")
    _write(tmp_path / "pkg" / "__init__.py")
    _write(tmp_path / "pkg" / "sub" / "deep.py")
    assert_structure(tmp_path)

    _write(tmp_path / "pkg" / "m12.py")
    with pytest.raises(AssertionError, match="pkg/: 13, the limit is 12"):
        assert_structure(tmp_path)


def test_without_a_line_limit_only_folders_are_measured(tmp_path):
    _write(tmp_path / "test_long.py", 900)
    for i in range(13):
        _write(tmp_path / "pkg" / f"test_{i}.py")
    assert measure(tmp_path, max_lines=None) == {"pkg/": 13}


def test_a_baseline_entry_tolerates_its_value_and_fails_when_it_grows(tmp_path):
    big = _write(tmp_path / "legacy.py", 200)
    assert_structure(tmp_path, baseline={"legacy.py": 200})

    _write(big, 201)
    with pytest.raises(AssertionError, match="legacy.py: grew to 201, its baseline is 200"):
        assert_structure(tmp_path, baseline={"legacy.py": 200})


def test_a_baseline_entry_must_follow_the_file_down(tmp_path):
    _write(tmp_path / "legacy.py", 180)
    with pytest.raises(AssertionError, match="shrank to 180, lower its baseline to 180"):
        assert_structure(tmp_path, baseline={"legacy.py": 200})

    _write(tmp_path / "legacy.py", 150)
    with pytest.raises(AssertionError, match="legacy.py: within the limit now, remove it"):
        assert_structure(tmp_path, baseline={"legacy.py": 200})


def test_domain_tests_may_import_the_domain_stdlib_pytest_and_their_own_helpers(tmp_path):
    root = tmp_path / "tests" / "unit" / "domain"
    _write(root / "helpers.py", text="import uuid")
    _write(root / "test_ok.py", text="\n".join([
        "from __future__ import annotations", "import pytest", "from domain.entities import Lead",
        "from tests.unit.domain.helpers import x", "import helpers", "from . import helpers",
        "from .helpers import x",
    ]))
    _write(root / "sub" / "test_nested.py", text="from .. import helpers")
    assert_domain_tests_isolated(root, "domain")


@pytest.mark.parametrize("statement", [
    "from application.ports import Port",
    "import psycopg",
    "from tests.unit.mocks.repo import Repo",
])
def test_domain_tests_must_not_import_anything_else(tmp_path, statement):
    root = tmp_path / "tests" / "unit" / "domain"
    _write(tmp_path / "tests" / "unit" / "mocks" / "repo.py")
    _write(root / "test_bad.py", text=statement)
    with pytest.raises(AssertionError, match=f"test_bad.py imports {statement.split()[1]}"):
        assert_domain_tests_isolated(root, "domain")


@pytest.mark.parametrize("statement, shown", [
    ("from .. import mocks", ".."),
    ("from ..mocks.repo import Repo", "..mocks.repo"),
])
def test_a_relative_import_that_leaves_the_domain_tests_fails(tmp_path, statement, shown):
    root = tmp_path / "tests" / "unit" / "domain"
    _write(tmp_path / "tests" / "unit" / "mocks" / "repo.py")
    _write(root / "test_bad.py", text=statement)
    with pytest.raises(AssertionError, match=f"test_bad.py imports {re.escape(shown)}$"):
        assert_domain_tests_isolated(root, "domain")


def test_the_command_line_checks_a_root_against_a_named_baseline(tmp_path, capsys):
    _write(tmp_path / "src" / "legacy.py", 200)
    baseline = _write(tmp_path / "baseline.py", text='LEGACY = {"legacy.py": 200}')
    root = str(tmp_path / "src")

    assert main(["check", root]) == 1
    assert main(["check", root, "--baseline", f"{baseline}:LEGACY"]) == 0
    assert main(["check", root, "--no-line-limit"]) == 0
    assert main(["measure", root]) == 0
    assert '"legacy.py": 200,' in capsys.readouterr().out
