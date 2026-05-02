"""Phase 2.0 milestone test: validate kobler goldens against the
new JSON Schema (`adapter-spec.schema.json`).

Runs as a unit test so `make test` and the CI workflow exercise it
automatically. Phase 2.1 will expand the scope to all 22 goldens.

Why a separate file (rather than extending `test_schema_contract.py`):
the contract test walks SKILL.md prose paths against a hand-curated
registry; this test runs `jsonschema` against actual golden YAML data.
They check different invariants and Phase 2 keeps both during the
migration window.
"""

from __future__ import annotations

import datetime
import json
import unittest
from pathlib import Path
from typing import Any

import yaml

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:
    raise unittest.SkipTest(f"jsonschema unavailable: {exc}")


# YAML auto-parses ISO 8601 timestamps to datetime. The schema declares
# timestamp_utc and similar as `string`, so normalize before validation.
def _normalize(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _normalize(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_normalize(v) for v in node]
    if isinstance(node, (datetime.datetime, datetime.date)):
        return node.isoformat()
    return node

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "adapter-spec.schema.json"


def _load_schema() -> dict:
    with open(SCHEMA_PATH) as fp:
        return json.load(fp)


def _load_golden(rel_path: str) -> Any:
    with open(REPO_ROOT / rel_path) as fp:
        return _normalize(yaml.safe_load(fp))


class TestSchemaSelfValidity(unittest.TestCase):
    """The schema itself must be a valid JSON Schema 2020-12 document."""

    def test_meta_schema_valid(self):
        schema = _load_schema()
        # check_schema raises if schema is not itself a valid 2020-12 schema
        Draft202012Validator.check_schema(schema)


class TestKoblerGoldensAgainstSchema(unittest.TestCase):
    """Phase 2.0 milestone: kobler-Go and kobler-Java validate cleanly.

    Phase 2.1 will expand to all 22 goldens. The schema is currently
    permissive on `code.*` and `tests.*` (`additionalProperties: true` on
    open maps); Phase 2.1 tightens these as taxonomy lands.
    """

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()
        cls.validator = Draft202012Validator(cls.schema)

    def _validate(self, rel_path: str) -> list:
        golden = _load_golden(rel_path)
        return sorted(self.validator.iter_errors(golden), key=lambda e: list(e.path))

    def test_kobler_go_golden_validates(self):
        errors = self._validate("prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml")
        self.assertEqual(
            errors, [],
            "kobler-Go golden must validate against the JSON Schema. "
            f"First 5 errors:\n" + "\n".join(
                f"  {'.'.join(str(p) for p in e.path) or '<root>'}: {e.message[:200]}"
                for e in errors[:5]
            ),
        )

    def test_kobler_java_golden_validates(self):
        errors = self._validate("prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml")
        self.assertEqual(
            errors, [],
            "kobler-Java golden must validate against the JSON Schema. "
            f"First 5 errors:\n" + "\n".join(
                f"  {'.'.join(str(p) for p in e.path) or '<root>'}: {e.message[:200]}"
                for e in errors[:5]
            ),
        )


if __name__ == "__main__":
    unittest.main()
