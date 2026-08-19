"""JSON Schema validation gate: every golden in the 40-spec corpus must
validate cleanly against `adapter-spec.schema.json` (Draft 2020-12).

Test classes:

- `TestSchemaSelfValidity` — schemas pass meta-schema check.
- `TestKoblerGoldensAgainstSchema` — kobler Go+Java sanity validation.
- `TestAllGoldensAgainstSchema` — all 42 goldens validate; if/then/else
  invariants enforced (source_language=go nulls Java-only blocks per
  ADR-001 + Wave 11b B4 C5; meta.is_alias=true Java specs null
  spring_config + bidder_class). Includes path-aware phantom-key
  detector (Wave 11b B5 #1 replaced the prior leaf-key escape).

Module-level helper `_build_declared_at(schema)` returns
`(declared_at, open_map_prefixes)` used by the path-aware phantom
detector — see its docstring for the cycle-guarded $ref + composition
union walk.

Why a separate file (rather than extending `test_schema_contract.py`):
the contract test walks SKILL.md prose paths against the schema's
path-keyed registry; this test runs `jsonschema` against actual golden
YAML data. They check different invariants and run independently.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

import yaml

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:
    raise unittest.SkipTest(f"jsonschema unavailable: {exc}")


# Wave 11b post-review fix: dates and datetimes in goldens MUST be quoted
# in the YAML source so that `yaml.safe_load` returns them as strings
# (matching the schema's `"type": "string"` declaration). Prior to this
# fix, the test ran a `_normalize()` step that converted Python datetime/
# date objects to ISO strings before validation — papering over a real
# issue: external consumers using stock JSON Schema validators would see
# every golden failed validation. The corpus is now stock-validator clean
# (provenance.read.timestamp_utc and lifecycle.rename.merged_at are
# quoted in every golden); _normalize() is removed to harden this
# invariant — adding an unquoted date in a future fixture will now
# surface as a schema validation failure instead of being silently
# rewritten by the test.

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared"
SCHEMA_PATH = SHARED_DIR / "adapter-spec.schema.json"

# All shared JSON Schemas in the repo. Each must be a well-formed
# Draft 2020-12 schema. Add new schemas here as they're authored
# (e.g., port-report.schema.json landed in Wave 8).
SHARED_SCHEMAS = (
    ("adapter-spec", SHARED_DIR / "adapter-spec.schema.json"),
    ("port-report", SHARED_DIR / "port-report.schema.json"),
)


def _load_schema(path: Path = SCHEMA_PATH) -> dict:
    with open(path) as fp:
        return json.load(fp)


def _load_golden(rel_path: str) -> Any:
    with open(REPO_ROOT / rel_path) as fp:
        return yaml.safe_load(fp)


def _build_declared_at(schema: dict) -> tuple[dict[str, set[str]], set[str]]:
    """Wave 11b B5 #1: Path-aware schema vocabulary builder.

    Walks the schema and returns:

    - `declared_at[prefix]` = set of property names declared at that exact
      JSONPath prefix. UNION across $ref expansion (cycle-guarded), and
      across composition keywords (oneOf/anyOf/allOf/if/then/else branches
      contribute at the SAME prefix).

    - `open_map_prefixes` = paths whose `additionalProperties` is `true`
      (or omitted per Draft 2020-12 default) on a `type: object` node.
      patternProperties also marks the prefix as open (any key admitted
      via the regex constraint).

    Array indices are NOT part of dotted paths — items at `prefix.field[]`
    contribute their property names to `declared_at[prefix.field]`.

    Used by test_no_truly_invented_keys_outside_open_maps to do path-aware
    phantom-key detection (replacing the prior global leaf-key escape
    that admitted property names regardless of path).
    """
    declared_at: dict[str, set[str]] = {}
    open_maps: set[str] = set()

    def walk(node, prefix: str, visiting: frozenset):
        if isinstance(node, dict) and "$ref" in node:
            ref = node["$ref"]
            if ref.startswith("#/$defs/"):
                ref_name = ref[len("#/$defs/"):]
                if ref_name in visiting:
                    return  # cycle guard for recursive $defs
                resolved = schema.get("$defs", {}).get(ref_name, {})
                walk(resolved, prefix, visiting | {ref_name})
            return
        if not isinstance(node, dict):
            return
        types = node.get("type")
        if isinstance(types, str):
            types = [types]
        is_object = isinstance(types, list) and "object" in types
        # Draft 2020-12: omitted additionalProperties defaults to True.
        addl = node.get("additionalProperties", True)
        is_open = addl is True or (isinstance(addl, dict) and addl)
        if (is_open or "patternProperties" in node) and is_object and prefix:
            open_maps.add(prefix)
        props = node.get("properties")
        if isinstance(props, dict):
            slot = declared_at.setdefault(prefix, set())
            for k, v in props.items():
                slot.add(k)
                child = f"{prefix}.{k}" if prefix else k
                walk(v, child, visiting)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, prefix, visiting)  # array items inherit parent prefix
        elif isinstance(items, list):
            for it in items:
                walk(it, prefix, visiting)
        for kw in ("oneOf", "anyOf", "allOf"):
            for branch in node.get(kw, []) or []:
                walk(branch, prefix, visiting)
        for kw in ("if", "then", "else"):
            if kw in node:
                walk(node[kw], prefix, visiting)

    walk(schema, "", frozenset())
    return declared_at, open_maps


class TestSchemaSelfValidity(unittest.TestCase):
    """Every shared JSON Schema must be a well-formed Draft 2020-12 document."""

    def test_meta_schema_valid(self):
        """All schemas in SHARED_SCHEMAS pass the meta-schema check.

        Parameterized over `SHARED_SCHEMAS` via subTest so a typo in any
        schema fails its own subTest with a clear message.
        """
        for name, path in SHARED_SCHEMAS:
            with self.subTest(schema=name, path=str(path.relative_to(REPO_ROOT))):
                self.assertTrue(path.is_file(), f"schema file missing: {path}")
                schema = _load_schema(path)
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
    """Every golden in the 40-spec corpus validates against the schema
    using a stock yaml.safe_load → jsonschema pipeline (no normalization
    layer). Wave 11b post-review fix: dates/datetimes are now quoted in
    the goldens so external consumers see the same byte-stable strings
    the schema declares.

    Implemented as a single test that aggregates results across all 40
    goldens. On failure, the message lists every failing golden + first
    error per golden for fast triage.
    """

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()
        cls.validator = Draft202012Validator(cls.schema)

    def test_stock_yaml_load_emits_strings_for_date_fields(self):
        """Wave 11b post-review regression gate: dates and datetimes in
        the goldens MUST parse as strings via stock `yaml.safe_load` (no
        normalization needed). External consumers using a stock JSON
        Schema validator depend on this.

        Asserts that `provenance.read.timestamp_utc` and
        `lifecycle.rename.merged_at` (when non-null) are str-typed for
        every golden. If any future fixture leaves a date unquoted, this
        test surfaces the regression before a downstream consumer hits
        it.
        """
        violations = []
        for p in _discover_goldens():
            with open(p) as fp:
                raw = yaml.safe_load(fp)  # stock loader, no normalize
            if not isinstance(raw, dict):
                continue
            ts = (raw.get("provenance") or {}).get("read") or {}
            ts_val = ts.get("timestamp_utc")
            if ts_val is not None and not isinstance(ts_val, str):
                violations.append(
                    f"{p.name}: provenance.read.timestamp_utc is {type(ts_val).__name__} "
                    f"(value={ts_val!r}); MUST be quoted in YAML to parse as str"
                )
            rename = (raw.get("lifecycle") or {}).get("rename") or {}
            ma_val = rename.get("merged_at")
            if ma_val is not None and not isinstance(ma_val, str):
                violations.append(
                    f"{p.name}: lifecycle.rename.merged_at is {type(ma_val).__name__} "
                    f"(value={ma_val!r}); MUST be quoted in YAML"
                )
        self.assertEqual(violations, [],
                         "Unquoted date/datetime fields detected:\n" + "\n".join(violations))

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
        """if/then/else discrimination: Go-source specs must null all Java-only blocks.

        Wave 11b B4 C5 expanded the invariant from {spring_config, bidder_class}
        to also include {code_naming, registry}. Corpus walk confirmed all 21
        Go specs emit null for all four fields; the schema's allOf now enforces.
        """
        violations = []
        for p in _discover_goldens():
            if "prebid-server-go" not in str(p):
                continue
            golden = _load_golden(str(p.relative_to(REPO_ROOT)))
            for field in ("spring_config", "bidder_class", "code_naming", "registry"):
                value = golden.get(field)
                if value is not None:
                    violations.append(f"{p.name} has non-null {field}")
        self.assertEqual(
            violations, [],
            "Go-source goldens must null Java-only blocks (ADR-001):\n"
            + "\n".join(f"  {v}" for v in violations),
        )

    def test_java_alias_specs_null_inheritable_blocks(self):
        """Wave 11b B4 C5: Java alias specs (meta.is_alias=true) must null
        spring_config and bidder_class — those fields are inherited from the
        parent and are never emitted on the alias spec itself. 152media-Java
        is the canonical alias example."""
        violations = []
        for p in _discover_goldens():
            if "prebid-server-java" not in str(p):
                continue
            golden = _load_golden(str(p.relative_to(REPO_ROOT)))
            meta = golden.get("meta") or {}
            if not meta.get("is_alias"):
                continue
            for field in ("spring_config", "bidder_class"):
                value = golden.get(field)
                if value is not None:
                    violations.append(f"{p.name} has non-null {field} on alias spec")
        self.assertEqual(
            violations, [],
            "Java alias specs must null spring_config + bidder_class:\n"
            + "\n".join(f"  {v}" for v in violations),
        )

    def test_if_then_invariants_reject_synthetic_violations(self):
        """Wave 11b B4 C5 enforcement: schema's allOf if/then clauses MUST
        reject synthetic violations (not just observe passive corpus
        compliance). Injects four bad-data variants and asserts each fails
        validation."""
        from copy import deepcopy
        from jsonschema import Draft202012Validator
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        validator = Draft202012Validator(schema)

        # Load a clean Go golden as baseline
        go_baseline = _load_golden("prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml")
        # Load a clean Java alias golden as baseline
        alias_baseline = _load_golden("prebid-server-java/read/test-fixtures/152media.golden.spec.yaml")

        cases = [
            ("Go spec with non-null code_naming", deepcopy(go_baseline) | {"code_naming": {"class_name_root": "Kobler"}}),
            ("Go spec with non-null registry", deepcopy(go_baseline) | {"registry": {"test_application_properties": {}}}),
            ("Java alias spec with non-null spring_config", deepcopy(alias_baseline) | {"spring_config": {"factory_class": "Foo"}}),
            ("Java alias spec with non-null bidder_class", deepcopy(alias_baseline) | {"bidder_class": {"name": "Foo"}}),
        ]
        for label, bad_spec in cases:
            errors = list(validator.iter_errors(bad_spec))
            self.assertGreater(
                len(errors), 0,
                f"Schema FAILED to reject: {label} — if/then enforcement is broken",
            )

    def test_no_truly_invented_keys_outside_open_maps(self):
        """Phase 2.3 phantom-path detector for goldens (Wave 11b B5 #1: PATH-AWARE).

        jsonschema's `iter_errors` accepts any key under blocks declared as
        `additionalProperties: true` (open maps), so a typo'd field there
        wouldn't fail validation. This test catches that case by cross-
        referencing every dotted path in every golden against the schema's
        path-aware vocabulary.

        ## Wave 11b B5 #1 architectural change

        Pre-Wave-11b detection had TWO load-bearing gaps:

        - GAP #1 (open-map prefix bypass): paths under any of the 28 open-
          map prefixes were silently admitted. CLOSED by Wave 11b B1/B2/B3/B3+
          (17 accidentally-open sites flipped to additionalProperties: false;
          11 prefixes remain — 4 EXTENSION-SLOTS + 7 LEGITIMATELY-OPEN).

        - GAP #2 (leaf-key permissive escape): `if k in known_keys` admitted
          ANY key whose name happened to appear anywhere in any
          $defs.*.properties block. So `code.builder = "request_body"` (a
          real property name from a totally unrelated $def) was accepted.
          REPLACED by path-aware vocabulary lookup (this commit, B5 #1).

        ## Path-aware detection

        `_build_declared_at(schema)` returns:

        - `declared_at: dict[prefix → set[property_names]]` — for every
          JSONPath prefix in the schema, the set of property names declared
          at that exact prefix. Walks $ref, oneOf/anyOf/allOf/if/then/else
          branches as union, with cycle guard for recursive $defs.

        - `open_maps: set[prefix]` — paths whose `additionalProperties` is
          `true` (or omitted per Draft 2020-12 default) on a `type: object`
          node. Includes patternProperties prefixes.

        For each leaf key at path `<prefix>.<k>`:

        - If under an open-map prefix → admit (permissive recursion)
        - Else if `k in declared_at.get(prefix, set())` → admit
        - Else → flag as phantom

        This closes Gap #2 entirely: keys are validated AT their path, not
        as a global vocabulary set. A spec with `code.builder = "request_body"`
        would now flag (request_body is declared under
        `$defs/MakeRequests` at prefix `code.make_requests`, NOT at
        prefix `code.builder` directly).
        """
        schema = _load_schema()
        declared_at, open_maps = _build_declared_at(schema)

        def under_open_map(path: str) -> bool:
            parts = path.split(".")
            for i in range(len(parts), 0, -1):
                prefix = ".".join(parts[:i])
                if prefix in open_maps:
                    return True
            return False

        invented: list = []
        for p in _discover_goldens():
            golden = _load_golden(str(p.relative_to(REPO_ROOT)))

            def walk(node, prefix=""):
                if isinstance(node, dict):
                    for k, v in node.items():
                        path = f"{prefix}.{k}" if prefix else k
                        # Permissive recursion under any open-map ancestor.
                        if prefix and under_open_map(prefix):
                            yield from walk(v, path)
                            continue
                        # Path-aware vocabulary lookup (closes Gap #2).
                        if k in declared_at.get(prefix, set()):
                            yield from walk(v, path)
                            continue
                        # Truly invented at this path.
                        yield (str(p.relative_to(REPO_ROOT)), path, k)
                        # Don't recurse — deeper mentions are downstream.
                elif isinstance(node, list):
                    for item in node:
                        yield from walk(item, prefix)

            invented.extend(walk(golden))

        if invented:
            lines = [f"{len(invented)} invented key(s) found in goldens:"]
            for golden, path, key in invented[:30]:
                lines.append(f"  {golden}: '{key}' at path {path}")
            self.fail("\n".join(lines))

    def test_path_aware_vocab_catches_gap2_cases(self):
        """Wave 11b B5 #1 regression gate: the path-aware vocabulary must
        catch the Gap #2 cases (key name appears under a different $def's
        prefix) that the prior leaf-key escape silently admitted.

        Synthesizes minimal `declared_at`/`open_maps` setups to exercise:

        - Path-aware acceptance: known property at the correct prefix.
        - Path-aware rejection: same key NAME under a wrong prefix where
          it isn't declared.
        - Open-map admission: any key under an open-map prefix.
        - Cycle guard: recursive $defs don't blow the stack.
        """
        schema = _load_schema()
        declared_at, open_maps = _build_declared_at(schema)

        # 1. `request_body` is declared under `code.make_requests`, not at
        #    `code.builder` (the Gap #2 example from the prior docstring).
        self.assertIn("request_body", declared_at.get("code.make_requests", set()),
                      "request_body must be declared at code.make_requests prefix")
        self.assertNotIn("request_body", declared_at.get("code.builder", set()),
                         "request_body must NOT be declared at code.builder "
                         "(Gap #2 case — the prior leaf-key escape admitted it)")

        # 2. Top-level fields contribute to declared_at[''].
        for top in ("meta", "bidder_info", "params", "code"):
            self.assertIn(top, declared_at.get("", set()),
                          f"top-level '{top}' missing from declared_at['']")

        # 3. Open-map prefixes still recognized (extension-slot example).
        # `provenance.read.skill_versions` is keyed by skill name with
        # patternProperties — should be in open_maps.
        # (One of the 11 remaining open-map prefixes post-Wave-11b.)
        self.assertTrue(
            any("skill_versions" in p for p in open_maps),
            "provenance.read.skill_versions should be open_map post-Wave-11b",
        )

        # 4. Closed schema blocks should NOT be in open_maps. Code was
        # closed in Wave 11b B1; it must have declared_at entries but NOT
        # appear in open_maps.
        self.assertNotIn("code", open_maps,
                         "code should NOT be open_map after Wave 11b B1 closure")
        self.assertIn("code", declared_at.get("", set()),
                      "code should be declared at top-level prefix")


class TestPortReportV020Invariants(unittest.TestCase):
    """Phase D review M-D + Tests-H1: commit the four schema-invariant
    cases that the M-D commit verified ad-hoc (the verification ran from a
    Python REPL but never landed as a checked-in test). Without these,
    the M-D tightenings — `pre_submit_rebase` if/then constraint and
    `source_pr_merged_commit_sha` pattern — could regress silently.
    """

    @classmethod
    def setUpClass(cls):
        port_report_schema_path = (
            Path(__file__).resolve().parents[2]
            / "prebid-server-go" / "read" / "skills" / "shared" / "port-report.schema.json"
        )
        with open(port_report_schema_path) as fp:
            cls.schema = json.load(fp)

    def _base_report(self) -> dict:
        return {
            "port_report_version": "0.2.0",
            "port_run": {
                "run_id": "2026-05-04T0001Z-test",
                "source_lang": "go",
                "target_lang": "java",
                "source_spec_sha": "a" * 64,
            },
            "r5_check": {"state": "pass"},
            "port_translation_rules_version": "0.2.0",
        }

    def test_pre_submit_rebase_with_conflict_and_summary_validates(self):
        from jsonschema import validate
        report = self._base_report()
        report["pre_submit_rebase"] = {
            "upstream_repo": "prebid/prebid-server-java",
            "base_sha_at_emit": "a" * 40,
            "base_sha_at_submit": "b" * 40,
            "conflicts_detected": True,
            "conflicts_summary": "rebase touched X file",
        }
        validate(report, self.schema)

    def test_pre_submit_rebase_with_conflict_but_null_summary_is_rejected(self):
        from jsonschema import ValidationError, validate
        report = self._base_report()
        report["pre_submit_rebase"] = {
            "upstream_repo": "prebid/prebid-server-java",
            "base_sha_at_emit": "a" * 40,
            "base_sha_at_submit": "b" * 40,
            "conflicts_detected": True,
            "conflicts_summary": None,
        }
        with self.assertRaises(ValidationError):
            validate(report, self.schema)

    def test_pre_submit_rebase_no_conflict_null_summary_validates(self):
        from jsonschema import validate
        report = self._base_report()
        report["pre_submit_rebase"] = {
            "upstream_repo": "prebid/prebid-server-java",
            "base_sha_at_emit": "a" * 40,
            "base_sha_at_submit": "b" * 40,
            "conflicts_detected": False,
            "conflicts_summary": None,
        }
        validate(report, self.schema)

    def test_pre_submit_rebase_with_conflict_and_empty_summary_is_rejected(self):
        """Beyond null: an empty string MUST also be rejected when conflicts
        are flagged true (the if/then constraint adds minLength: 1)."""
        from jsonschema import ValidationError, validate
        report = self._base_report()
        report["pre_submit_rebase"] = {
            "upstream_repo": "prebid/prebid-server-java",
            "base_sha_at_emit": "a" * 40,
            "base_sha_at_submit": "b" * 40,
            "conflicts_detected": True,
            "conflicts_summary": "",
        }
        with self.assertRaises(ValidationError):
            validate(report, self.schema)

    def test_source_pr_merged_commit_sha_empty_string_rejected(self):
        from jsonschema import ValidationError, validate
        report = self._base_report()
        report["source_pr_merged_commit_sha"] = ""
        with self.assertRaises(ValidationError):
            validate(report, self.schema)

    def test_source_pr_merged_commit_sha_40_hex_validates(self):
        from jsonschema import validate
        report = self._base_report()
        report["source_pr_merged_commit_sha"] = "a" * 40
        validate(report, self.schema)

    def test_source_pr_merged_commit_sha_null_validates(self):
        """Per type ['string', 'null'] — null is a valid alternative to a
        40-hex string. Confirms the M-D fix didn't accidentally close out
        the legitimate null-equivalent path."""
        from jsonschema import validate
        report = self._base_report()
        report["source_pr_merged_commit_sha"] = None
        validate(report, self.schema)

    def test_r5_check_state_six_state_enum(self):
        """Phase D 0.2.0 schema admits six r5_check.state values."""
        from jsonschema import validate, ValidationError
        for state in (
            "pass",
            "warn-byte-only-divergence",
            "warn-target-strengthens-source",
            "fail-semantic-divergence",
            "fail-source-omits-target-constraint",
            "skipped-no-pair-fixture",
        ):
            report = self._base_report()
            report["r5_check"] = {"state": state}
            validate(report, self.schema)
        # Non-enum values rejected.
        report = self._base_report()
        report["r5_check"] = {"state": "bogus-state"}
        with self.assertRaises(ValidationError):
            validate(report, self.schema)


# ---------------------------------------------------------------------------
# The version a reader is told to emit must be one the schema can validate.
# ---------------------------------------------------------------------------

CURRENT_SPEC_VERSION = "2.0.0"

# Skills that instruct a reader to write adapter_spec_version. Both orchestrators
# now do; before 2.0.0 only the Java one did, and it named a version whose
# required-field set a new read no longer satisfies.
VERSION_EMITTING_SKILLS = (
    "prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md",
    "prebid-server-java/read/skills/read-bidder-orchestrator/SKILL.md",
)


def _version_emit_findings() -> list[str]:
    import re
    bad = []
    for rel in VERSION_EMITTING_SKILLS:
        path = str(REPO_ROOT / rel)
        if not Path(path).is_file():
            bad.append(f"{rel}: missing")
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        emitted = set(re.findall(r'adapter_spec_version:\s*[`"]?"?(\d+\.\d+\.\d+)"?', text))
        if not emitted:
            bad.append(f"{rel}: does not state which adapter_spec_version to emit, "
                       f"and it is a required property")
        elif emitted != {CURRENT_SPEC_VERSION}:
            bad.append(f"{rel}: instructs emitting {sorted(emitted)}, "
                       f"current is {CURRENT_SPEC_VERSION}")
    return bad


class TestEmittedSpecVersion(unittest.TestCase):
    """A reader told to emit an older version writes a spec that contradicts
    itself: 2.0.0 is the version that REQUIRES bidder_params_ref, and the reader
    emits a ref either way. Before this check the Java orchestrator said 1.0.0
    and the Go one said nothing at all about a required field."""

    def test_both_orchestrators_name_the_current_version(self):
        bad = _version_emit_findings()
        self.assertEqual([], bad, "\n  ".join(bad))

    def test_that_version_is_the_one_the_schema_admits(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        pattern = schema["properties"]["adapter_spec_version"].get("pattern")
        self.assertIsNotNone(pattern, "adapter_spec_version lost its pattern constraint")
        self.assertRegex(CURRENT_SPEC_VERSION, pattern)  # noqa: the pattern IS the constraint
        self.assertIn("bidder_params_ref", schema["required"],
                      "CURRENT_SPEC_VERSION is 2.0.0 because the ref is required; "
                      "if the ref stopped being required, this constant is stale")

    def test_every_golden_declares_it(self):
        wrong = []
        goldens = sorted(
            list((REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures").glob("*.golden.spec.yaml"))
            + list((REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures").glob("*.golden.spec.yaml")))
        self.assertTrue(goldens, "no goldens discovered -- an empty scan is a setup error")
        for f in goldens:
            got = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("adapter_spec_version")
            if got != CURRENT_SPEC_VERSION:
                wrong.append(f"{f.relative_to(REPO_ROOT).as_posix()}: {got!r}")
        self.assertEqual([], wrong, "\n  ".join(wrong))



if __name__ == "__main__":
    unittest.main()
