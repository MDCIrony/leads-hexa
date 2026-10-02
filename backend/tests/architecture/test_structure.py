"""Code structure rule (ADR-0037): file size, folder width and domain-test isolation."""
from pathlib import Path

from chassis.testing import assert_domain_tests_isolated, assert_structure

from tests.architecture.structure_baseline import BASELINE

_BACKEND = Path(__file__).resolve().parents[2]


def test_source_files_and_folders_stay_within_the_limits_or_their_baseline():
    assert_structure(_BACKEND / "src", baseline=BASELINE)


def test_domain_tests_import_only_the_domain():
    assert_domain_tests_isolated(_BACKEND / "tests" / "unit" / "domain", "domain")
