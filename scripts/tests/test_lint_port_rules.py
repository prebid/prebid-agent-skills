"""Phase 2.6 unit tests for scripts/lib/lint-port-rules.py.

Synthetic specs exercise positive/negative cases per rule. A few real-golden
spot-checks confirm the lint produces the expected verdicts on shipped data.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_PATH = REPO_ROOT / "scripts" / "lib" / "lint-port-rules.py"

spec = importlib.util.spec_from_file_location("lint_port_rules", LINT_PATH)
if spec is None or spec.loader is None:
    raise unittest.SkipTest(f"Cannot load {LINT_PATH}")
lpr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lpr)


def _spec(**overrides) -> dict:
    """Build a minimal valid spec dict with optional overrides."""
    base: dict = {
        "meta": {"bidder_name": "synthetic", "is_alias": False, "alias_of": None},
        "code": {"make_requests": {}},
        "tests": {"fixture_inventory": {"exemplary": [], "integration": []}},
        "bidder_params_sha256": None,
    }
    # Shallow-merge override at top-level + 1 level for meta/code/tests
    for k, v in overrides.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return base


class TestRule5MutationStrategies(unittest.TestCase):
    """Rule 5: Site/App entity_strategies pairing."""

    def test_canonical_pair_passes(self):
        go = _spec(code={"make_requests": {"mutation": {"entity_strategies": {"Site": "copy-then-mutate", "App": "copy-then-mutate"}}}})
        java = _spec(code={"make_requests": {"mutation": {"entity_strategies": {"Site": "immutable-rebuild", "App": "immutable-rebuild"}}}})
        findings = lpr.rule_5_mutation_strategies(go, java)
        self.assertEqual(2, len(findings))
        self.assertTrue(all(f.severity == "pass" for f in findings))

    def test_in_place_to_immutable_rebuild_also_passes(self):
        go = _spec(code={"make_requests": {"mutation": {"entity_strategies": {"Site": "in-place"}}}})
        java = _spec(code={"make_requests": {"mutation": {"entity_strategies": {"Site": "immutable-rebuild"}}}})
        findings = lpr.rule_5_mutation_strategies(go, java)
        self.assertEqual(1, len(findings))
        self.assertEqual("pass", findings[0].severity)

    def test_unexpected_pair_warns(self):
        go = _spec(code={"make_requests": {"mutation": {"entity_strategies": {"Site": "copy-then-mutate"}}}})
        java = _spec(code={"make_requests": {"mutation": {"entity_strategies": {"Site": "in-place"}}}})  # Java should never use in-place
        findings = lpr.rule_5_mutation_strategies(go, java)
        self.assertEqual(1, len(findings))
        self.assertEqual("warn", findings[0].severity)
        self.assertIn("entity_strategies.Site", findings[0].message)

    def test_none_on_both_sides_silent(self):
        go = _spec()
        java = _spec()
        findings = lpr.rule_5_mutation_strategies(go, java)
        self.assertEqual(0, len(findings))

    def test_none_string_normalizes_to_none(self):
        # aax pattern: Java has 'none' string; Go has missing field
        go = _spec()
        java = _spec(code={"make_requests": {"mutation": {"entity_strategies": {"Site": "none", "App": "none"}}}})
        findings = lpr.rule_5_mutation_strategies(go, java)
        # 'none' normalizes to None; both sides treated as null → silent
        self.assertEqual(0, len(findings))


class TestRule9CustomRequestBody(unittest.TestCase):
    """Rule 9: Custom-typed request body coherence."""

    def test_both_passthrough_passes(self):
        go = _spec(code={"make_requests": {"request_body": {"kind": "openrtb2-passthrough"}}})
        java = _spec(bidder_class={"parameterized_request_type": "BidRequest"})
        findings = lpr.rule_9_custom_request_body(go, java)
        self.assertEqual(1, len(findings))
        self.assertEqual("pass", findings[0].severity)

    def test_both_modified_passes(self):
        go = _spec(code={"make_requests": {"request_body": {"kind": "openrtb2-modified"}}})
        java = _spec(bidder_class={"parameterized_request_type": "BidRequest"})
        findings = lpr.rule_9_custom_request_body(go, java)
        self.assertEqual("pass", findings[0].severity)

    def test_both_custom_passes(self):
        go = _spec(code={"make_requests": {"request_body": {"kind": "custom"}}})
        java = _spec(bidder_class={"parameterized_request_type": "MediasquareRequest"})
        findings = lpr.rule_9_custom_request_body(go, java)
        self.assertEqual(1, len(findings))
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("MediasquareRequest", findings[0].message)

    def test_asymmetry_warns(self):
        go = _spec(code={"make_requests": {"request_body": {"kind": "custom"}}})
        java = _spec(bidder_class={"parameterized_request_type": "BidRequest"})  # Java says passthrough
        findings = lpr.rule_9_custom_request_body(go, java)
        self.assertEqual("warn", findings[0].severity)
        self.assertIn("custom-body asymmetry", findings[0].message)

    def test_alias_skipped(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        findings = lpr.rule_9_custom_request_body(go, java)
        self.assertEqual(0, len(findings))


class TestRule33AliasInversion(unittest.TestCase):
    """Rule 33: Go aliasOf ↔ Java parent.aliases[] coherence."""

    def test_alias_listed_in_parent_passes(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        parent_spec = _spec(meta={"bidder_name": "parent"}, aliases=[{"name": "child"}])
        findings = lpr.rule_33_alias_inversion(go, java, {"parent": parent_spec})
        self.assertEqual(1, len(findings))
        self.assertEqual("pass", findings[0].severity)

    def test_alias_string_form_in_parent_passes(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        parent_spec = _spec(meta={"bidder_name": "parent"}, aliases=["child"])
        findings = lpr.rule_33_alias_inversion(go, java, {"parent": parent_spec})
        self.assertEqual("pass", findings[0].severity)

    def test_alias_missing_from_parent_warns(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        parent_spec = _spec(meta={"bidder_name": "parent"}, aliases=[{"name": "other"}])
        findings = lpr.rule_33_alias_inversion(go, java, {"parent": parent_spec})
        self.assertEqual("warn", findings[0].severity)

    def test_no_parent_in_scope_passes_best_effort(self):
        go = _spec(meta={"bidder_name": "152media", "is_alias": True, "alias_of": "adkernel"})
        java = _spec(meta={"bidder_name": "152media", "is_alias": True, "alias_of": "adkernel"})
        findings = lpr.rule_33_alias_inversion(go, java, {})
        self.assertEqual(1, len(findings))
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("not in scope", findings[0].message)

    def test_non_alias_skipped(self):
        go = _spec(meta={"bidder_name": "kobler"})
        java = _spec(meta={"bidder_name": "kobler"})
        findings = lpr.rule_33_alias_inversion(go, java, {})
        self.assertEqual(0, len(findings))

    def test_alias_without_parent_name_warns(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": None})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": None})
        findings = lpr.rule_33_alias_inversion(go, java, {})
        self.assertEqual("warn", findings[0].severity)


class TestRule36FixtureParity(unittest.TestCase):
    """Rule 36: Both languages have fixture inventories."""

    def test_both_populated_passes(self):
        go = _spec(tests={"fixture_inventory": {"exemplary": ["a.json", "b.json"], "integration": []}})
        java = _spec(tests={"fixture_inventory": {"exemplary": [], "integration": ["x", "y", "z", "w"]}})
        findings = lpr.rule_36_test_fixture_parity(go, java)
        self.assertEqual("pass", findings[0].severity)

    def test_one_sided_warns(self):
        go = _spec(tests={"fixture_inventory": {"exemplary": ["a.json"]}})
        java = _spec(tests={"fixture_inventory": {"integration": []}})
        findings = lpr.rule_36_test_fixture_parity(go, java)
        self.assertEqual("warn", findings[0].severity)
        self.assertIn("asymmetry", findings[0].message)

    def test_alias_passes_with_zero_exemplary(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"},
                   tests={"fixture_inventory": {"exemplary": []}})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"},
                     tests={"fixture_inventory": {"integration": ["x", "y", "z", "w"]}})
        findings = lpr.rule_36_test_fixture_parity(go, java)
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("Rule 37", findings[0].message)

    def test_both_empty_passes(self):
        findings = lpr.rule_36_test_fixture_parity(_spec(), _spec())
        self.assertEqual("pass", findings[0].severity)


class TestRule38ByteFidelity(unittest.TestCase):
    """Rule 38: bidder_params_sha256 byte-equality."""

    def test_matching_sha_passes(self):
        sha = "a" * 64
        go = _spec(bidder_params_sha256=sha)
        java = _spec(bidder_params_sha256=sha)
        findings = lpr.rule_38_bidder_params_byte_fidelity(go, java)
        self.assertEqual("pass", findings[0].severity)

    def test_diverging_sha_warns(self):
        go = _spec(bidder_params_sha256="a" * 64)
        java = _spec(bidder_params_sha256="b" * 64)
        findings = lpr.rule_38_bidder_params_byte_fidelity(go, java)
        self.assertEqual("warn", findings[0].severity)

    def test_one_sided_sha_warns(self):
        go = _spec(bidder_params_sha256="a" * 64)
        java = _spec(bidder_params_sha256=None)
        findings = lpr.rule_38_bidder_params_byte_fidelity(go, java)
        self.assertEqual("warn", findings[0].severity)
        self.assertIn("one-sided", findings[0].message)

    def test_both_absent_silent(self):
        findings = lpr.rule_38_bidder_params_byte_fidelity(_spec(), _spec())
        self.assertEqual(0, len(findings))


class TestRule44AliasEmpire(unittest.TestCase):
    """Rule 44: Empire alias-flavor coherence."""

    def test_no_flavor_skipped(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        findings = lpr.rule_44_alias_empire(go, java, {})
        self.assertEqual(0, len(findings))  # not classified as empire

    def test_flavor_match_passes(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent",
                           "empire_parent_flavor": "white-label-saas"})
        parent_spec = _spec(meta={"bidder_name": "parent"},
                            aliases=[{"name": "child", "relationship_flavor": "white-label-saas"}])
        findings = lpr.rule_44_alias_empire(go, java, {"parent": parent_spec})
        self.assertEqual("pass", findings[0].severity)

    def test_flavor_mismatch_warns(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent",
                           "empire_parent_flavor": "white-label-saas"})
        parent_spec = _spec(meta={"bidder_name": "parent"},
                            aliases=[{"name": "child", "relationship_flavor": "registration-only"}])
        findings = lpr.rule_44_alias_empire(go, java, {"parent": parent_spec})
        self.assertEqual("warn", findings[0].severity)
        self.assertIn("empire-flavor mismatch", findings[0].message)

    def test_missing_in_parent_warns(self):
        go = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent"})
        java = _spec(meta={"bidder_name": "child", "is_alias": True, "alias_of": "parent",
                           "empire_parent_flavor": "white-label-saas"})
        parent_spec = _spec(meta={"bidder_name": "parent"}, aliases=[{"name": "other"}])
        findings = lpr.rule_44_alias_empire(go, java, {"parent": parent_spec})
        self.assertEqual("warn", findings[0].severity)
        self.assertIn("does not list", findings[0].message)


class TestRule46Naming(unittest.TestCase):
    """Rule 46: Naming-convention normalization."""

    def test_identical_names_pass(self):
        findings = lpr.rule_46_naming_normalization(
            _spec(meta={"bidder_name": "kobler"}),
            _spec(meta={"bidder_name": "kobler"}),
        )
        self.assertEqual("pass", findings[0].severity)

    def test_lowercase_transformation_passes(self):
        findings = lpr.rule_46_naming_normalization(
            _spec(meta={"bidder_name": "audienceNetwork"}),
            _spec(meta={"bidder_name": "audiencenetwork"}),
        )
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("lowercase", findings[0].message)

    def test_underscore_drop_passes(self):
        findings = lpr.rule_46_naming_normalization(
            _spec(meta={"bidder_name": "boldwin_rapid"}),
            _spec(meta={"bidder_name": "boldwinrapid"}),
        )
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("underscore-drop", findings[0].message)

    def test_hyphen_drop_passes(self):
        findings = lpr.rule_46_naming_normalization(
            _spec(meta={"bidder_name": "freewheel-ssp"}),
            _spec(meta={"bidder_name": "freewheelssp"}),
        )
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("hyphen-drop", findings[0].message)

    def test_digit_leading_workaround_passes(self):
        findings = lpr.rule_46_naming_normalization(
            _spec(meta={"bidder_name": "33across"}),
            _spec(meta={"bidder_name": "thirtythreeacross"}),
        )
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("digit-leading-workaround", findings[0].message)

    def test_brand_acronym_passes_when_declared(self):
        dual = {"naming_asymmetry": {"transformation": "brand-acronym-preservation"}}
        findings = lpr.rule_46_naming_normalization(
            _spec(meta={"bidder_name": "MyBrand"}),
            _spec(meta={"bidder_name": "MyBrand1"}),
            dual,
        )
        self.assertEqual("pass", findings[0].severity)
        self.assertIn("brand-acronym-preservation", findings[0].message)

    def test_undeclared_name_divergence_warns(self):
        findings = lpr.rule_46_naming_normalization(
            _spec(meta={"bidder_name": "foobar"}),
            _spec(meta={"bidder_name": "foobaz"}),  # not a mechanical normalization
        )
        self.assertEqual("warn", findings[0].severity)
        self.assertIn("Rule 46 violation", findings[0].message)


class TestLintPairOnRealGoldens(unittest.TestCase):
    """Spot-check that the lint produces expected verdicts on shipped goldens."""

    def setUp(self):
        self.pairs = lpr.discover_pairs()
        self.pairs_by_bidder = {p[0]: p for p in self.pairs}

    def test_kobler_pair_clean_except_rule_38_passes(self):
        """kobler is the only golden with matching shas — Rule 38 should pass."""
        self.assertIn("kobler", self.pairs_by_bidder)
        bidder, go, java, dual = self.pairs_by_bidder["kobler"]
        findings = lpr.lint_pair(go, java, dual, {})
        rule_38 = [f for f in findings if f.rule_id == 38]
        self.assertEqual(1, len(rule_38))
        self.assertEqual("pass", rule_38[0].severity)

    def test_mediasquare_rule_9_custom_passes(self):
        """mediasquare is the canonical Rule 9 custom-body case."""
        self.assertIn("mediasquare", self.pairs_by_bidder)
        bidder, go, java, dual = self.pairs_by_bidder["mediasquare"]
        findings = lpr.lint_pair(go, java, dual, {})
        rule_9 = [f for f in findings if f.rule_id == 9]
        self.assertEqual(1, len(rule_9))
        self.assertEqual("pass", rule_9[0].severity)
        self.assertIn("custom-body coherent", rule_9[0].message)

    def test_152media_alias_rule_46_passes(self):
        """152media has matching go==java names ('152media'); Rule 46 is trivially satisfied."""
        self.assertIn("152media", self.pairs_by_bidder)
        bidder, go, java, dual = self.pairs_by_bidder["152media"]
        findings = lpr.lint_pair(go, java, dual, {})
        rule_46 = [f for f in findings if f.rule_id == 46]
        self.assertEqual(1, len(rule_46))
        self.assertEqual("pass", rule_46[0].severity)

    def test_overall_no_failures_on_shipped_goldens(self):
        """Shipped goldens MUST NOT have any Rule failure (only pass/warn)."""
        java_parents = {b: j for (b, _g, j, _d) in self.pairs if not (j.get("meta", {}) or {}).get("is_alias")}
        all_findings = []
        for bidder, go, java, dual in self.pairs:
            all_findings.extend(lpr.lint_pair(go, java, dual, java_parents))
        fails = [f for f in all_findings if f.severity == "fail"]
        self.assertEqual([], fails, f"Shipped goldens have {len(fails)} Rule failure(s): {fails}")


if __name__ == "__main__":
    unittest.main()
