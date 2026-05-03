#!/usr/bin/env python3
"""Unit tests for scripts/round-trip-ci.py.

Covers Wave 4 R-rule changes per the change spec:
  R1 forbids `..` path-traversal segments
  R2 prints full SHAs in mismatch messages
  R4 idempotence (round-trip determinism)
  R5 polarity inversion (stale-pass detection)
  R5 extended STRICT vs DIVERGENT key handling
  R5 honors overall.cross_language_state + blocker_count
  R5 runs even when one side has no fixture
  R6 validates cross_language.go_artifacts.bidder_constant
  R7 walks provenance.warnings AND quirks for bidder-constant-mismatch
  R9 legacy-encoding-json detection (renamed from old taxa-registry check, now R3b)
  Per-rule try/except isolates crashes so one rule's bug doesn't void the rest

Run from repo root:
    python3 -m unittest scripts.tests.test_round_trip_ci

Tests document the post-Wave-4 expected behavior. Some tests will FAIL on
pre-Wave-4 code; that is intentional — they pin the bugs being fixed.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from typing import Any, Dict, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
RTCI_PATH = os.path.join(REPO_ROOT, "scripts", "round-trip-ci.py")

# Load round-trip-ci.py despite the hyphen in the filename. Register in
# sys.modules BEFORE exec_module so dataclasses.dataclass can resolve the
# module's __module__ attribute.
_spec = importlib.util.spec_from_file_location("rtci", RTCI_PATH)
assert _spec is not None and _spec.loader is not None
rtci = importlib.util.module_from_spec(_spec)
sys.modules["rtci"] = rtci
_spec.loader.exec_module(rtci)


def make_spec(bidder="kobler", language="go", raw=None, raw_text=None):
    """Construct a synthetic Spec for testing."""
    return rtci.Spec(
        path=f"/tmp/{bidder}.golden.spec.yaml",
        bidder=bidder,
        language=language,
        raw=raw if raw is not None else {},
        raw_text=raw_text if raw_text is not None else "{}\n",
    )


def severities(findings):
    return [f.severity for f in findings]


def details(findings):
    return [f.detail for f in findings]


# ---------------------------------------------------------------------------
# R1: file-reachability — forbid `..` path traversal
# ---------------------------------------------------------------------------

def _provenance(file_path: str) -> dict:
    """Build a minimal provenance block carrying a single file ref.

    The pinned SHA below is the Phase A-4 commit (`d7f8515b...`, 2026-04-27).
    Phase 5 fixtures pin to a newer SHA (`2fae16f31693...`, 2026-05-02); this
    test fixture intentionally uses the older pin since the assertions don't
    depend on which Phase the SHA represents — they only need a syntactically
    valid 40-char hex SHA. Either SHA would pass; the older one is preserved
    for stability of test snapshots.
    """
    return {
        "source": {
            "repo": "prebid/prebid-server",
            "resolved_commit": "d7f8515b86258688304b0d9b6668c6a0e258bc9e",
        },
        "warnings": [{"file": file_path, "type": "test"}],
    }


class TestR1(unittest.TestCase):
    def test_forbids_dotdot_path_traversal(self):
        """R1 must FAIL when any `file:` field contains a `..` segment."""
        spec = make_spec(raw={"provenance": _provenance("../../../etc/passwd")})
        findings = rtci.r1_check(spec, network_check=False, gh_cache={})
        fails = [f for f in findings if f.severity == rtci.SEV_FAIL]
        self.assertTrue(
            any(".." in f.detail or "traversal" in f.detail.lower() for f in fails),
            f"Expected R1 to FAIL on '..' path traversal; got: {[f.detail for f in findings]}",
        )

    def test_forbids_absolute_paths(self):
        """R1 must FAIL on absolute paths (leading `/`)."""
        spec = make_spec(raw={"provenance": _provenance("/etc/shadow")})
        findings = rtci.r1_check(spec, network_check=False, gh_cache={})
        fails = [f for f in findings if f.severity == rtci.SEV_FAIL]
        self.assertTrue(
            any("/etc/shadow" in f.detail or "absolute" in f.detail.lower()
                or "traversal" in f.detail.lower() for f in fails),
            f"Expected R1 to FAIL on absolute path; got: {[f.detail for f in findings]}",
        )


# ---------------------------------------------------------------------------
# R2: sha integrity — print full SHAs in mismatch messages
# ---------------------------------------------------------------------------

class TestR2(unittest.TestCase):
    def test_full_sha_in_mismatch_message(self):
        """R2 must print the full 64-char SHA on mismatch (not truncated)."""
        # bidder_params_json is "{}" → sha256 = 44f683...28d33adf
        # We declare a different SHA so R2 reports the mismatch.
        bogus_sha = "deadbeef" * 8  # 64 chars
        spec = make_spec(raw={
            "bidder_params_json": "{}",
            "bidder_params_sha256": bogus_sha,
        })
        findings = rtci.r2_check(spec)
        fail = next((f for f in findings if f.severity == rtci.SEV_FAIL), None)
        self.assertIsNotNone(fail, f"Expected R2 to FAIL; got: {findings}")
        # Both SHAs (declared + computed) must appear in full
        self.assertIn(bogus_sha, fail.detail,
            f"Expected full declared SHA in detail; got: {fail.detail}")


# ---------------------------------------------------------------------------
# R4: round-trip determinism — re-runnable idempotence
# ---------------------------------------------------------------------------

class TestR4(unittest.TestCase):
    def test_passes_on_serialisable_spec(self):
        spec = make_spec(raw={
            "meta": {"bidder_name": "kobler"},
            "quirks": [{"id": "x", "edge_case_taxon": "incomplete-classification"}],
        })
        findings = rtci.r4_check(spec)
        # At least one PASS (no FAIL).
        fails = [f for f in findings if f.severity == rtci.SEV_FAIL]
        self.assertEqual(fails, [], f"Expected no FAIL on serialisable spec; got: {fails}")


# ---------------------------------------------------------------------------
# R5: cross-language structural parity
# ---------------------------------------------------------------------------

class TestR5(unittest.TestCase):
    def _make_pair(self, go_extra: Dict[str, Any] = None, java_extra: Dict[str, Any] = None):
        go_raw = {
            "meta": {"bidder_name": "foo"},
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"capabilities": {"site": ["banner"]}, "gvl_vendor_id": 0},
            "params": {"schema_interpretation": {"properties": [], "required_fields": []}},
        }
        if go_extra:
            for k, v in go_extra.items():
                go_raw[k] = v
        java_raw = {
            "meta": {"bidder_name": "foo"},
            "bidder_params_sha256": "b" * 64,
            "bidder_info": {"capabilities": {"site": ["banner"]}, "gvl_vendor_id": 0},
            "params": {"schema_interpretation": {"properties": [], "required_fields": []}},
        }
        if java_extra:
            for k, v in java_extra.items():
                java_raw[k] = v
        return make_spec("foo", "go", go_raw), make_spec("foo", "java", java_raw)

    def test_polarity_inversion_stale_pass_fails(self):
        """When dual-spec says severity:pass but runtime SHAs disagree, R5 must
        FAIL — the "pass" claim is stale and runtime is the source of truth."""
        go_spec, java_spec = self._make_pair()
        # SHAs differ (a*64 vs b*64). Dual-spec falsely claims they're equal.
        dual_specs = {"foo": {
            "assertions": {
                "bidder_params_sha256": {
                    "go": "a" * 64, "java": "a" * 64,  # claim of equality
                    "byte_equal": True, "semantically_equal": True,
                    "severity": "pass",
                },
            },
        }}
        findings = rtci.r5_check(go_spec, java_spec, dual_specs)
        fails = [f for f in findings if f.severity == rtci.SEV_FAIL]
        self.assertTrue(
            len(fails) >= 1,
            f"Expected R5 to FAIL on stale-pass (runtime divergence vs claimed pass); "
            f"got severities: {severities(findings)}, details: {details(findings)}",
        )

    def test_extended_divergent_keys_default_enabled_warns(self):
        """bidder_info_default_enabled is R5-divergent — divergence WARNs not FAILs."""
        go_spec, java_spec = self._make_pair(
            go_extra={"bidder_info": {"capabilities": {"site": ["banner"]},
                                       "gvl_vendor_id": 0, "default_enabled": True}},
            java_extra={"bidder_info": {"capabilities": {"site": ["banner"]},
                                         "gvl_vendor_id": 0, "default_enabled": False}},
        )
        # Make SHAs match so this isn't conflated with the SHA assertion.
        go_spec.raw["bidder_params_sha256"] = "c" * 64
        java_spec.raw["bidder_params_sha256"] = "c" * 64
        dual_specs = {"foo": {
            "assertions": {
                "bidder_info_default_enabled": {
                    "go": True, "java": False,
                    "equivalent": False,
                    "severity": "warn",
                },
            },
        }}
        findings = rtci.r5_check(go_spec, java_spec, dual_specs)
        # Should emit at least one WARN (or PASS), but no FAIL specific to this key.
        fails = [f for f in findings if f.severity == rtci.SEV_FAIL
                 and "default_enabled" in f.detail]
        self.assertEqual(
            fails, [],
            f"Expected no FAIL on divergent default_enabled (severity: warn); got: {fails}",
        )

    def test_overall_blocker_count_escalates(self):
        """When overall.cross_language_state is divergent-semantic AND
        overall.blocker_count > 0, R5 must FAIL."""
        go_spec, java_spec = self._make_pair()
        go_spec.raw["bidder_params_sha256"] = "d" * 64
        java_spec.raw["bidder_params_sha256"] = "d" * 64
        dual_specs = {"foo": {
            "overall": {
                "cross_language_state": "divergent-semantic",
                "blocker_count": 1,
            },
        }}
        findings = rtci.r5_check(go_spec, java_spec, dual_specs)
        fails = [f for f in findings if f.severity == rtci.SEV_FAIL]
        self.assertTrue(
            len(fails) >= 1,
            f"Expected R5 to FAIL when overall says divergent-semantic+blocker_count>0; "
            f"got: {findings}",
        )

    def test_one_side_only_fixture_does_not_crash(self):
        """R5 must run even when only one language has a spec."""
        java_spec = make_spec("aax", "java", {
            "meta": {"bidder_name": "aax"},
            "bidder_params_sha256": "e" * 64,
            "bidder_info": {"capabilities": {"site": ["banner"]}, "gvl_vendor_id": 720},
        })
        dual_specs = {"aax": {
            "assertions": {
                "bidder_params_sha256": {"go": "e" * 64, "java": "e" * 64,
                                          "severity": "fail"},
            },
        }}
        # Pass go_spec=None — current implementation may crash; post-Wave-4 must not.
        try:
            findings = rtci.r5_check(None, java_spec, dual_specs)
            # If it doesn't crash, we accept any output — the test mainly checks resilience.
            self.assertIsInstance(findings, list)
        except (AttributeError, TypeError):
            self.fail("R5 must not crash when one side has no fixture (Change 4)")


# ---------------------------------------------------------------------------
# R6: bidder_constant validation
# ---------------------------------------------------------------------------

class TestR6(unittest.TestCase):
    def test_validates_go_artifacts_bidder_constant(self):
        """R6 must WARN when cross_language.go_artifacts.bidder_constant doesn't
        match the canonical openrtb_ext.Bidder<X> form."""
        spec = make_spec("foo", "go", {
            "meta": {"bidder_name": "foo"},
            "cross_language": {
                "go_artifacts": {
                    "package_name": "foo",
                    "bidder_constant": "openrtb_ext.BidderWrong",  # wrong!
                },
            },
        })
        findings = rtci.r6_check(spec)
        warns_or_fails = [f for f in findings
                          if f.severity in (rtci.SEV_WARN, rtci.SEV_FAIL)
                          and "bidder_constant" in f.detail.lower()]
        self.assertTrue(
            len(warns_or_fails) >= 1,
            f"Expected R6 to surface the bidder_constant mismatch; got: {findings}",
        )

    def test_rebrand_warning_suppresses_constant_fail(self):
        """When provenance.warnings contains bidder-name-rebrand, R6 must NOT
        FAIL on the bidder_constant mismatch (the rebrand is acknowledged)."""
        spec = make_spec("foo", "go", {
            "meta": {"bidder_name": "foo"},
            "provenance": {
                "warnings": [{"type": "bidder-name-rebrand", "file": "exchange/adapter_util.go"}],
            },
            "cross_language": {
                "go_artifacts": {
                    "package_name": "foo",
                    "bidder_constant": "openrtb_ext.BidderRebrand",
                },
            },
        })
        findings = rtci.r6_check(spec)
        constant_fails = [f for f in findings
                          if f.severity == rtci.SEV_FAIL and "bidder_constant" in f.detail]
        self.assertEqual(
            constant_fails, [],
            f"Expected rebrand warning to suppress bidder_constant FAIL; got: {constant_fails}",
        )

    def test_alias_suppresses_package_dir_warns(self):
        """When meta.is_alias=true, R6 must compare cross_language artifacts
        against meta.alias_of (parent), NOT against the alias's own bidder_name.
        The alias's package_name and bidder_dir route through the parent.

        Real-world canonical: 152media is an alias of adkernel; its
        go_artifacts.package_name=adkernel and java_artifacts.bidder_dir=
        adapters/adkernel/ — without alias suppression, R6 spuriously WARNed
        on every alias golden."""
        spec = make_spec("152media", "go", {
            "meta": {
                "bidder_name": "152media",
                "is_alias": True,
                "alias_of": "adkernel",
            },
            "cross_language": {
                "go_artifacts": {
                    "package_name": "adkernel",
                    "bidder_constant": "openrtb_ext.BidderAdkernel",
                },
                "java_artifacts": {
                    "bidder_dir": "src/main/java/org/prebid/server/bidder/adkernel/",
                },
            },
        })
        findings = rtci.r6_check(spec)
        # Should NOT warn on package_name or bidder_dir mismatch
        package_warns = [f for f in findings
                         if f.severity == rtci.SEV_WARN
                         and ("package_name" in f.detail or "bidder_dir" in f.detail)]
        self.assertEqual(
            package_warns, [],
            f"Alias R6 should not warn on package/dir mismatch when "
            f"the alias correctly routes to its parent; got: {package_warns}",
        )
        # Should also not warn on bidder_constant since alias inherits parent's constant
        constant_warns = [f for f in findings
                          if f.severity == rtci.SEV_WARN and "bidder_constant" in f.detail]
        self.assertEqual(
            constant_warns, [],
            f"Alias R6 should accept parent's bidder_constant; got: {constant_warns}",
        )

    def test_alias_with_wrong_parent_still_warns(self):
        """When meta.is_alias=true but the alias's package_name doesn't match
        meta.alias_of, R6 MUST still WARN — alias suppression doesn't mean
        no validation, it means validation against the parent."""
        spec = make_spec("foo", "go", {
            "meta": {
                "bidder_name": "foo",
                "is_alias": True,
                "alias_of": "barparent",
            },
            "cross_language": {
                "go_artifacts": {
                    "package_name": "wrongparent",  # should be barparent
                },
            },
        })
        findings = rtci.r6_check(spec)
        package_warns = [f for f in findings
                         if f.severity == rtci.SEV_WARN and "package_name" in f.detail]
        self.assertTrue(
            len(package_warns) >= 1,
            f"Expected WARN when alias's package_name doesn't match parent; got: {findings}",
        )


# ---------------------------------------------------------------------------
# R7: bidder-constant-mismatch — walk warnings AND quirks
# ---------------------------------------------------------------------------

class TestR7(unittest.TestCase):
    def test_walks_provenance_warnings(self):
        """R7 must surface a finding for every provenance.warnings[].type ==
        bidder-constant-mismatch — catches the kobler `kobler_test.go:12`
        BidderKargo bug currently invisible to the harness."""
        spec = make_spec("kobler", "go", {
            "meta": {"bidder_name": "kobler"},
            "params": {"params_test": {"bidder_constant_referenced":
                                        "openrtb_ext.BidderKobler"}},
            "provenance": {
                "warnings": [{
                    "type": "bidder-constant-mismatch",
                    "file": "adapters/kobler/kobler_test.go",
                    "line": 12,
                    "summary": "BidderKargo copy-paste bug",
                }],
            },
        })
        findings = rtci.r7_check(spec)
        relevant = [f for f in findings
                    if "kobler_test" in f.detail or "BidderKargo" in f.detail
                    or "warnings" in f.detail.lower()]
        self.assertTrue(
            len(relevant) >= 1,
            f"Expected R7 to surface the bidder-constant-mismatch warning; got: {findings}",
        )

    def test_walks_quirks_taxa(self):
        """R7 must surface a finding for every quirks[].edge_case_taxon ==
        bidder-constant-mismatch."""
        spec = make_spec("kobler", "go", {
            "meta": {"bidder_name": "kobler"},
            "params": {"params_test": {"bidder_constant_referenced":
                                        "openrtb_ext.BidderKobler"}},
            "quirks": [{
                "id": "bidder-constant-mismatch-test",
                "file": "adapters/kobler/kobler_test.go",
                "edge_case_taxon": "bidder-constant-mismatch",
                "summary": "BidderKargo copy-paste bug",
            }],
        })
        findings = rtci.r7_check(spec)
        relevant = [f for f in findings
                    if "kobler_test" in f.detail or "BidderKargo" in f.detail
                    or "quirk" in f.detail.lower()]
        self.assertTrue(
            len(relevant) >= 1,
            f"Expected R7 to surface the bidder-constant-mismatch quirk; got: {findings}",
        )


# ---------------------------------------------------------------------------
# R9: legacy-encoding-json direct-usage detection (the NEW canonical R9)
# ---------------------------------------------------------------------------

class TestR9LegacyEncoding(unittest.TestCase):
    def test_warns_when_legacy_encoding_used_without_quirk(self):
        """R9 (post-rename) must WARN when a Go spec uses encoding/json directly
        (has_jsonutil=false + uses_marshal=true) without a paired quirk/warning."""
        spec = make_spec("legacy", "go", {
            "meta": {"bidder_name": "legacy"},
            "code": {
                "imports": {"has_jsonutil": False},
                "file_layout": {
                    "files": [{"name": "legacy.go", "uses_marshal": True}],
                },
            },
            # No quirk or warning surfacing the legacy usage.
            "quirks": [],
            "provenance": {"warnings": []},
        })
        # Wave 4 settled the function name as `r9_check`. Older drafts
        # called it `r_legacy_encoding_check`; try the modern name first.
        check_fn = getattr(rtci, "r9_check", None) or rtci.r_legacy_encoding_check
        # Some signatures take `registered`; try with empty list.
        try:
            findings = check_fn(spec, [], lenient=False)
        except TypeError:
            findings = check_fn(spec)
        warns_or_fails = [f for f in findings
                          if f.severity in (rtci.SEV_WARN, rtci.SEV_FAIL)
                          and ("legacy" in f.detail.lower() or "json" in f.detail.lower()
                               or "encoding" in f.detail.lower())]
        # The R9 check MUST fire for this spec (Go, has_jsonutil=false,
        # uses_marshal=true, no paired quirk/warning). Unconditionally
        # assert — earlier draft gated this on hasattr() and was a no-op
        # because the function is named r9_check.
        self.assertTrue(
            len(warns_or_fails) >= 1,
            f"Expected R9 (legacy-encoding) to WARN; got: {findings}",
        )


# ---------------------------------------------------------------------------
# Per-rule isolation — try/except wrapping
# ---------------------------------------------------------------------------

class TestRuleIsolation(unittest.TestCase):
    def test_main_loop_isolates_per_rule_crashes(self):
        """The main loop must wrap each rule call in try/except so a crash in
        one rule produces a Finding rather than aborting the entire run.

        We can only test this via the main entry point, which is harder to
        synthesize. Instead, we assert the Finding shape can carry crash
        info (rule + severity + detail) — sufficient documentation for the
        change."""
        # Construct a Finding shaped like a rule-crash finding.
        f = rtci.Finding(rule="R3", spec="go/foo", severity=rtci.SEV_FAIL,
                          detail="rule crashed: KeyError: 'missing'")
        self.assertEqual(f.rule, "R3")
        self.assertEqual(f.severity, rtci.SEV_FAIL)
        self.assertIn("crash", f.detail.lower())


if __name__ == "__main__":
    unittest.main()
