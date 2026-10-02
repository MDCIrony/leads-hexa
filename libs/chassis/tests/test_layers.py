from chassis.testing import imported_roots, layer_violations, stdlib_only_violations


def _write(root, relative, source):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_imported_roots_takes_the_first_segment_and_skips_relative_imports(tmp_path):
    path = _write(tmp_path, "m.py", "import a.b\nfrom c.d import e\nfrom . import f\nfrom .g import h\n")

    assert imported_roots(path) == {"a", "c"}


def test_layer_violations_detects_both_import_forms(tmp_path):
    _write(tmp_path, "domain/one.py", "import application.x\n")
    _write(tmp_path, "domain/sub/two.py", "from infrastructure import y\n")
    _write(tmp_path, "domain/clean.py", "import os\n")

    assert layer_violations(tmp_path, "domain", {"application", "infrastructure"}) == [
        "domain/one.py imports application",
        "domain/sub/two.py imports infrastructure",
    ]


def test_layer_violations_ignores_relative_imports(tmp_path):
    _write(tmp_path, "domain/one.py", "from . import application\nfrom .infrastructure import y\n")

    assert layer_violations(tmp_path, "domain", {"application", "infrastructure"}) == []


def test_layer_violations_only_looks_inside_the_layer(tmp_path):
    _write(tmp_path, "application/use.py", "import infrastructure.db\n")

    assert layer_violations(tmp_path, "domain", {"infrastructure"}) == []


def test_stdlib_only_accepts_stdlib_future_and_allowed_roots(tmp_path):
    _write(tmp_path, "domain/ok.py", "from __future__ import annotations\nfrom dataclasses import dataclass\nimport domain.x\n")

    assert stdlib_only_violations(tmp_path, "domain", {"domain"}) == []


def test_stdlib_only_rejects_third_party(tmp_path):
    _write(tmp_path, "domain/bad.py", "import pydantic\nimport os\n")

    assert stdlib_only_violations(tmp_path, "domain", {"domain"}) == ["domain/bad.py imports pydantic"]
