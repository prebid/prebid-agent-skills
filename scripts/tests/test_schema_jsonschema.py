"""Phase 2.0 + 2.1 milestone test: validate every golden against the
new JSON Schema (`adapter-spec.schema.json`).

Phase 2.0: kobler-Go and kobler-Java validate cleanly.
Phase 2.1: ALL 22 goldens validate cleanly + if/then/else discrimination
on `source_language` ensures Go specs null spring_config/bidder_class.

Runs as a unit test so `make test` and the CI workflow exercise it
automatically.

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
    Retained as a smoke test independent of the all-goldens run below.
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


def _discover_goldens():
    """Discover all golden spec YAMLs under prebid-server-{go,java}/read/test-fixtures/."""
    paths = []
    for lang_dir in ("prebid-server-go", "prebid-server-java"):
        d = REPO_ROOT / lang_dir / "read" / "test-fixtures"
        for p in sorted(d.glob("*.golden.spec.yaml")):
            paths.append(p)
    return paths


class TestAllGoldensAgainstSchema(unittest.TestCase):
    """Phase 2.1 milestone: every golden validates against the schema.

    Implemented as a single test that aggregates results across all 22
    goldens. On failure, the message lists every failing golden + first
    error per golden for fast triage.
    """

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()
        cls.validator = Draft202012Validator(cls.schema)

    def test_all_22_goldens_validate(self):
        paths = _discover_goldens()
        self.assertGreater(len(paths), 0, "no goldens discovered")
        failures = {}
        for p in paths:
            golden = _load_golden(str(p.relative_to(REPO_ROOT)))
            errors = sorted(
                self.validator.iter_errors(golden),
                key=lambda e: list(e.path),
            )
            if errors:
                rel = str(p.relative_to(REPO_ROOT))
                failures[rel] = errors
        if failures:
            lines = [
                f"{len(failures)} of {len(paths)} goldens failed schema validation:",
            ]
            for rel, errors in failures.items():
                lines.append(f"  {rel}: {len(errors)} errors")
                for e in errors[:3]:
                    p_str = ".".join(str(x) for x in e.path) or "<root>"
                    lines.append(f"    [{p_str}] {e.message[:200]}")
            self.fail("\n".join(lines))

    def test_go_specs_have_null_java_only_blocks(self):
        """if/then/else discrimination: Go-source specs must null spring_config + bidder_class."""
        violations = []
        for p in _discover_goldens():
            if "prebid-server-go" not in str(p):
                continue
            golden = _load_golden(str(p.relative_to(REPO_ROOT)))
            for field in ("spring_config", "bidder_class"):
                value = golden.get(field)
                if value is not None:
                    violations.append(f"{p.name} has non-null {field}")
        self.assertEqual(
            violations, [],
            "Go-source goldens must null Java-only blocks (ADR-001):\n"
            + "\n".join(f"  {v}" for v in violations),
        )


if __name__ == "__main__":
    unittest.main()
