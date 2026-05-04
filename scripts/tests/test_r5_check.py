#!/usr/bin/env python3
"""Unit tests for scripts/lib/r5_check.py.

Lib-level tests covering the public API exposed for the upcoming Phase D
port skills:

- ``compare_pair`` end-to-end across pass / warn / fail scenarios.
- ``aggregate_state`` four-state reduction.
- ``SpecView`` duck typing (a minimal stand-in object works as input).
- Helper functions (``deep_eq``, ``_list_set_eq``, ``_maintainer_eq``,
  ``normalize_endpoint_macros``) edge cases. The harness-side tests at
  ``scripts/tests/test_round_trip_ci.py`` exercise these via re-exports;
  this file covers the lib-level callable contract directly.

Run from repo root:
    python3 -m pytest scripts/tests/test_r5_check.py
"""

from __future__ import annotations

import dataclasses
import unittest
from typing import Any, Dict, Optional

from scripts.lib import r5_check
from scripts.lib.r5_check import (
    FAIL,
    PASS,
    R5_PORT_STATES,
    R5Diagnostic,
    R5Result,
    STATE_FAIL_SEMANTIC,
    STATE_PASS,
    STATE_SKIPPED_NO_PAIR,
    STATE_WARN_BYTE_ONLY,
    WARN,
    aggregate_state,
    compare_pair,
    deep_eq,
    normalize_endpoint_macros,
)


@dataclasses.dataclass
class FakeSpec:
    """Minimal SpecView implementation for tests; mirrors the shape of the
    harness ``Spec`` dataclass without pulling round-trip-ci.py into
    sys.path.
    """

    bidder: str
    raw: Dict[str, Any]

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node


def make_spec(bidder: str = "kobler", raw: Optional[Dict[str, Any]] = None) -> FakeSpec:
    return FakeSpec(bidder=bidder, raw=raw or {})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestDeepEq(unittest.TestCase):
    def test_equal_dicts(self):
        self.assertTrue(deep_eq({"a": 1, "b": 2}, {"b": 2, "a": 1}))

    def test_unequal_dicts(self):
        self.assertFalse(deep_eq({"a": 1}, {"a": 2}))

    def test_lists_are_order_sensitive(self):
        # deep_eq compares JSON-serialized representation; lists with
        # different order are unequal under deep_eq itself.
        self.assertFalse(deep_eq([1, 2, 3], [3, 2, 1]))

    def test_none_equals_none(self):
        self.assertTrue(deep_eq(None, None))


class TestListSetEq(unittest.TestCase):
    def test_set_equal_lists_pass(self):
        self.assertTrue(r5_check._list_set_eq(["site", "app"], ["app", "site"]))

    def test_unequal_lists_fail(self):
        self.assertFalse(r5_check._list_set_eq(["site"], ["site", "app"]))

    def test_nested_dict_members(self):
        a = [{"k": 1}, {"k": 2}]
        b = [{"k": 2}, {"k": 1}]
        self.assertTrue(r5_check._list_set_eq(a, b))

    def test_mixed_falls_through(self):
        self.assertFalse(r5_check._list_set_eq(None, []))
        self.assertTrue(r5_check._list_set_eq(None, None))


class TestMaintainerEq(unittest.TestCase):
    def test_email_only_invariant(self):
        a = {"email": "a@example.com", "team": "Bid"}
        b = {"email": "A@Example.com", "phone": "+1"}
        self.assertTrue(r5_check._maintainer_eq(a, b))

    def test_different_email(self):
        self.assertFalse(r5_check._maintainer_eq({"email": "x"}, {"email": "y"}))

    def test_missing_email_compares_empty(self):
        self.assertTrue(r5_check._maintainer_eq({"team": "Bid"}, {}))


class TestNormalizeEndpointMacros(unittest.TestCase):
    def test_go_template_form(self):
        self.assertEqual(normalize_endpoint_macros("https://x.com/{{.Host}}/bid"),
                         "https://x.com/{{Host}}/bid")

    def test_java_property_form(self):
        self.assertEqual(normalize_endpoint_macros("https://x.com/${host}/bid"),
                         "https://x.com/{{host}}/bid")

    def test_spring_el_form(self):
        self.assertEqual(normalize_endpoint_macros("https://x.com/#{host}/bid"),
                         "https://x.com/{{host}}/bid")

    def test_already_canonical(self):
        self.assertEqual(normalize_endpoint_macros("https://x.com/{{host}}/bid"),
                         "https://x.com/{{host}}/bid")

    def test_non_string_passthrough(self):
        self.assertEqual(normalize_endpoint_macros(42), 42)
        self.assertIsNone(normalize_endpoint_macros(None))


# ---------------------------------------------------------------------------
# compare_pair: pair-presence
# ---------------------------------------------------------------------------


class TestComparePairPresence(unittest.TestCase):
    def test_both_none_returns_skipped(self):
        result = compare_pair(None, None)
        self.assertEqual(result.state, STATE_SKIPPED_NO_PAIR)
        self.assertEqual(result.diagnostics, [])

    def test_one_side_only_returns_skipped_state(self):
        java = make_spec(raw={"bidder_params_sha256": "abc"})
        result = compare_pair(None, java)
        self.assertEqual(result.state, STATE_SKIPPED_NO_PAIR)

    def test_both_sides_with_byte_equal_sha_passes(self):
        sha = "0" * 64
        go = make_spec(raw={"bidder_params_sha256": sha})
        java = make_spec(raw={"bidder_params_sha256": sha})
        result = compare_pair(go, java)
        self.assertEqual(result.state, STATE_PASS)
        keys = {d.key for d in result.diagnostics if d.severity == PASS}
        self.assertIn("bidder_params_sha256", keys)


# ---------------------------------------------------------------------------
# compare_pair: divergence + assertions
# ---------------------------------------------------------------------------


class TestComparePairDivergence(unittest.TestCase):
    def test_byte_only_divergence_with_assertion_warns(self):
        go = make_spec(raw={"bidder_params_sha256": "a" * 64})
        java = make_spec(raw={"bidder_params_sha256": "b" * 64})
        assertions = {"bidder_params_sha256": {
            "severity": "warn",
            "semantically_equal": True,
            "divergence_kind": "byte-only-whitespace",
        }}
        result = compare_pair(go, java, assertions=assertions)
        self.assertEqual(result.state, STATE_WARN_BYTE_ONLY)
        diag = next(d for d in result.diagnostics if d.key == "bidder_params_sha256")
        self.assertEqual(diag.severity, WARN)
        self.assertEqual(diag.category, "byte-only-divergence")

    def test_semantic_divergence_with_assertion_fails(self):
        go = make_spec(raw={"bidder_params_sha256": "a" * 64})
        java = make_spec(raw={"bidder_params_sha256": "b" * 64})
        assertions = {"bidder_params_sha256": {
            "severity": "fail",
            "semantically_equal": False,
            "divergence_kind": "semantic",
        }}
        result = compare_pair(go, java, assertions=assertions)
        self.assertEqual(result.state, STATE_FAIL_SEMANTIC)
        diag = next(d for d in result.diagnostics if d.key == "bidder_params_sha256")
        self.assertEqual(diag.severity, FAIL)
        self.assertEqual(diag.category, "semantic-divergence")

    def test_stale_pass_assertion_fails(self):
        """If runtime SHAs differ but dual-spec claims byte-equal, FAIL."""
        go = make_spec(raw={"bidder_params_sha256": "a" * 64})
        java = make_spec(raw={"bidder_params_sha256": "b" * 64})
        assertions = {"bidder_params_sha256": {"severity": "pass"}}
        result = compare_pair(go, java, assertions=assertions)
        self.assertEqual(result.state, STATE_FAIL_SEMANTIC)
        diag = next(d for d in result.diagnostics if d.key == "bidder_params_sha256")
        self.assertEqual(diag.category, "stale-pass")

    def test_strict_key_runtime_divergence_fails(self):
        go = make_spec(raw={
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"capabilities": {"site": {"mediaTypes": ["banner"]}}},
        })
        java = make_spec(raw={
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"capabilities": {"app": {"mediaTypes": ["video"]}}},
        })
        result = compare_pair(go, java)
        self.assertEqual(result.state, STATE_FAIL_SEMANTIC)
        keys = {d.key for d in result.diagnostics if d.severity == FAIL}
        self.assertIn("bidder_info.capabilities", keys)

    def test_form_divergent_normalized_equal_passes(self):
        """Go {{.Host}} and Java ${host} normalize to {{Host}}/{{host}}; case
        differs but normalization preserves macro names — they're not equal
        either way. Use a case-matching example to verify normalization."""
        go = make_spec(raw={
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"endpoint": "https://x/{{.Host}}/bid"},
        })
        java = make_spec(raw={
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"endpoint": "https://x/${Host}/bid"},
        })
        result = compare_pair(go, java)
        self.assertEqual(result.state, STATE_PASS)

    def test_form_divergent_assertion_missing_fails(self):
        """When normalized endpoint forms differ AND no dual-spec entry, FAIL."""
        go = make_spec(raw={
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"endpoint": "https://go.example/{{.Host}}/bid"},
        })
        java = make_spec(raw={
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"endpoint": "https://java.example/${host}/bid"},
        })
        result = compare_pair(go, java)
        self.assertEqual(result.state, STATE_FAIL_SEMANTIC)
        diag = next(d for d in result.diagnostics if d.key == "bidder_info.endpoint")
        self.assertEqual(diag.category, "assertion-missing")


class TestComparePairOverall(unittest.TestCase):
    def test_overall_divergent_semantic_with_blockers_fails(self):
        sha = "0" * 64
        go = make_spec(raw={"bidder_params_sha256": sha})
        java = make_spec(raw={"bidder_params_sha256": sha})
        result = compare_pair(go, java, overall={
            "cross_language_state": "divergent-semantic",
            "blocker_count": 1,
        })
        self.assertEqual(result.state, STATE_FAIL_SEMANTIC)
        keys = {d.key for d in result.diagnostics if d.severity == FAIL}
        self.assertIn("overall.cross_language_state", keys)

    def test_overall_no_blockers_no_finding(self):
        sha = "0" * 64
        go = make_spec(raw={"bidder_params_sha256": sha})
        java = make_spec(raw={"bidder_params_sha256": sha})
        result = compare_pair(go, java, overall={
            "cross_language_state": "convergent",
            "blocker_count": 0,
        })
        self.assertEqual(result.state, STATE_PASS)


# ---------------------------------------------------------------------------
# aggregate_state
# ---------------------------------------------------------------------------


class TestAggregateState(unittest.TestCase):
    def test_pair_absent_returns_skipped(self):
        state, byte_eq, warn, fail = aggregate_state([], pair_present=False)
        self.assertEqual(state, STATE_SKIPPED_NO_PAIR)
        self.assertEqual(byte_eq, [])
        self.assertEqual(warn, [])
        self.assertEqual(fail, [])

    def test_empty_diagnostics_passes(self):
        state, _, warn, fail = aggregate_state([], pair_present=True)
        self.assertEqual(state, STATE_PASS)
        self.assertEqual(warn, [])
        self.assertEqual(fail, [])

    def test_pass_only_yields_pass(self):
        diags = [R5Diagnostic("k1", PASS, "ok"), R5Diagnostic("k2", PASS, "ok")]
        state, byte_eq, _, _ = aggregate_state(diags, pair_present=True)
        self.assertEqual(state, STATE_PASS)
        self.assertEqual(set(byte_eq), {"k1", "k2"})

    def test_warn_yields_warn_byte_only(self):
        diags = [R5Diagnostic("k1", PASS, "ok"), R5Diagnostic("k2", WARN, "diverges")]
        state, byte_eq, warn, _ = aggregate_state(diags, pair_present=True)
        self.assertEqual(state, STATE_WARN_BYTE_ONLY)
        self.assertEqual(byte_eq, ["k1"])
        self.assertEqual(warn, ["k2"])

    def test_any_fail_yields_fail_semantic(self):
        diags = [
            R5Diagnostic("k1", PASS, "ok"),
            R5Diagnostic("k2", WARN, "diverges"),
            R5Diagnostic("k3", FAIL, "semantic"),
        ]
        state, byte_eq, warn, fail = aggregate_state(diags, pair_present=True)
        self.assertEqual(state, STATE_FAIL_SEMANTIC)
        self.assertEqual(fail, ["k3"])
        # Lists are produced regardless of state precedence.
        self.assertEqual(byte_eq, ["k1"])
        self.assertEqual(warn, ["k2"])


# ---------------------------------------------------------------------------
# Schema state vocabulary
# ---------------------------------------------------------------------------


class TestStateVocabulary(unittest.TestCase):
    def test_port_states_enum_complete(self):
        # Lock in the schema enum so a future drop/rename trips a test.
        self.assertEqual(set(R5_PORT_STATES), {
            "pass",
            "warn-byte-only-divergence",
            "warn-target-strengthens-source",
            "fail-semantic-divergence",
            "fail-source-omits-target-constraint",
            "skipped-no-pair-fixture",
        })


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class TestR5Result(unittest.TestCase):
    def test_result_is_dataclass_with_two_fields(self):
        result = R5Result(diagnostics=[], state=STATE_PASS)
        self.assertEqual(result.state, STATE_PASS)
        self.assertEqual(result.diagnostics, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
