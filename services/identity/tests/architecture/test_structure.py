"""Code structure rule (ADR-0037): file size, folder width and domain-test isolation. No baseline."""
from pathlib import Path

from chassis.testing import assert_domain_tests_isolated, assert_structure

_SERVICE = Path(__file__).resolve().parents[2]


def test_source_files_and_folders_stay_within_the_limits():
    assert_structure(_SERVICE / "src")


def test_test_folders_stay_within_the_folder_limit():
    # Tests have no line limit; a folder of dozens of mixed test files is as hard to read as one of sources.
    assert_structure(_SERVICE / "tests", max_lines=None)


def test_domain_tests_import_only_the_domain():
    assert_domain_tests_isolated(_SERVICE / "tests" / "unit" / "domain", "domain")
