"""Command line for the structure rule, so every root of the repository is checked the same way.

    python -m chassis.testing measure ROOT [--no-line-limit]
    python -m chassis.testing check ROOT [--no-line-limit] [--baseline FILE[:NAME]]

`measure` prints what is over the limits in baseline form; `check` asserts it.
A baseline file is a Python module holding a dict, `BASELINE` unless NAME says otherwise."""
import argparse
import runpy
import sys
from typing import Optional

from chassis.testing.structure import MAX_LINES, assert_structure, measure


def _baseline(spec: Optional[str]) -> dict:
    if not spec:
        return {}
    path, _, name = spec.partition(":")
    return runpy.run_path(path)[name or "BASELINE"]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m chassis.testing")
    parser.add_argument("command", choices=["measure", "check"])
    parser.add_argument("root")
    parser.add_argument("--no-line-limit", action="store_true", help="for tests: only the folder limit applies")
    parser.add_argument("--baseline", help="FILE[:NAME], a module holding the baseline dict")
    args = parser.parse_args(argv)
    max_lines = None if args.no_line_limit else MAX_LINES
    if args.command == "measure":
        for path, count in measure(args.root, max_lines=max_lines).items():
            print(f'    "{path}": {count},')
        return 0
    try:
        assert_structure(args.root, max_lines=max_lines, baseline=_baseline(args.baseline))
    except AssertionError as error:
        print(f"FAIL {args.root}\n{error}", file=sys.stderr)
        return 1
    print(f"ok   {args.root}")
    return 0
