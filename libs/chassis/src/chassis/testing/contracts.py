"""Contract helpers (`contracts/` at the repository root): fixtures and JSON Schema checks.

`jsonschema` is imported on first use, so a service that never checks a
contract does not need it installed."""
import json
from pathlib import Path


def contracts_root() -> Path:
    """The `contracts/` directory holding a README.md, searched upwards from the
    working directory and from this file. In Docker it is mounted at /srv/contracts
    or /contracts, both ancestors of every service's tree."""
    for start in (Path.cwd().resolve(), Path(__file__).resolve()):
        for base in (start, *start.parents):
            if (base / "contracts" / "README.md").is_file():
                return base / "contracts"
    raise FileNotFoundError(
        "contracts/ not found: mount the repository's contracts/ at /srv/contracts or /contracts")


def load_fixture(relative: str) -> dict:
    """A fixture by its path under `contracts/fixtures/`, e.g. "events/AgentState.v1.json"."""
    return json.loads((contracts_root() / "fixtures" / relative).read_text(encoding="utf-8"))


def assert_conforms(payload: dict, schema: str) -> None:
    """Fails unless `payload` conforms to the schema at `schema`, a path under
    `contracts/` such as "events/AgentState.v1.schema.json"."""
    from jsonschema import Draft202012Validator
    from referencing import Registry
    from referencing.jsonschema import DRAFT202012

    root = contracts_root()
    resources = []
    for path in sorted(root.rglob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        resources.append((document["$id"], DRAFT202012.create_resource(document)))
    registry = Registry().with_resources(resources)
    target = json.loads((root / schema).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(target, registry=registry).iter_errors(payload), key=str)
    assert not errors, f"{schema} not conformed:\n" + "\n".join(
        f"  {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors)
