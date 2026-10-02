"""Code structure rule (ADR-0037): file size, folder width and domain-test isolation."""
from pathlib import Path

from chassis.testing import assert_domain_tests_isolated, assert_structure

from tests.architecture import structure_baseline, tests_structure_baseline

_BACKEND = Path(__file__).resolve().parents[2]


def test_source_files_and_folders_stay_within_the_limits_or_their_baseline():
    assert_structure(_BACKEND / "src", baseline=structure_baseline.BASELINE)


def test_test_folders_stay_within_the_folder_limit_or_their_baseline():
    # Tests have no line limit; a folder of dozens of mixed test files is as hard to read as one of sources.
    assert_structure(_BACKEND / "tests", max_lines=None, baseline=tests_structure_baseline.BASELINE)


def test_domain_tests_import_only_the_domain():
    assert_domain_tests_isolated(_BACKEND / "tests" / "unit" / "domain", "domain")
