"""Prints the structure baseline of a source tree: `python -m chassis.testing src`."""
import sys

from chassis.testing.structure import measure

for path, count in measure(sys.argv[1]).items():
    print(f'    "{path}": {count},')
