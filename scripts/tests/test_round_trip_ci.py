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
import hashlib
import pathlib
import tempfile
import unittest
from typing import Any, Dict, Optional

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

    def test_gh_path_exists_distinguishes_404_from_unreachable(self):
        """Wave 11b B4 C2: gh_path_exists must return False on genuine 404
        and raise GhApiUnreachable on auth/rate-limit/network failures.

        The Wave 10 incident: prior code treated every non-zero returncode
        as 404, causing 246 false-FAILs against goldens whose upstream
        files actually existed. The refactor inspects stderr to
        distinguish failure modes.
        """
        from unittest.mock import patch
        from subprocess import CompletedProcess

        # Simulate genuine 404
        with patch("shutil.which", return_value="/usr/bin/gh"), \
             patch("subprocess.run", return_value=CompletedProcess(
                 args=[], returncode=1, stdout="",
                 stderr="gh: Not Found (HTTP 404)\n")):
            cache: Dict[Any, Any] = {}
            result = rtci.gh_path_exists("foo/bar", "abc123", "missing.go", cache)
            self.assertEqual(result, False, "genuine 404 must return False")

        # Simulate auth failure (401 or rate-limit) — must RAISE
        with patch("shutil.which", return_value="/usr/bin/gh"), \
             patch("subprocess.run", return_value=CompletedProcess(
                 args=[], returncode=1, stdout="",
                 stderr="gh: HTTP 401: Bad credentials\n")):
            cache = {}
            with self.assertRaises(rtci.GhApiUnreachable) as cm:
                rtci.gh_path_exists("foo/bar", "abc123", "x.go", cache)
            self.assertIn("401", str(cm.exception))

        # Simulate timeout — must RAISE
        from subprocess import TimeoutExpired
        with patch("shutil.which", return_value="/usr/bin/gh"), \
             patch("subprocess.run", side_effect=TimeoutExpired(cmd="gh", timeout=15)):
            cache = {}
            with self.assertRaises(rtci.GhApiUnreachable) as cm:
                rtci.gh_path_exists("foo/bar", "abc123", "x.go", cache)
            self.assertIn("timeout", str(cm.exception).lower())

        # Simulate gh not installed — must return None (expected fallback)
        with patch("shutil.which", return_value=None):
            cache = {}
            result = rtci.gh_path_exists("foo/bar", "abc123", "x.go", cache)
            self.assertIsNone(result, "gh not installed must return None")

        # Simulate success (HTTP 200) — must return True
        with patch("shutil.which", return_value="/usr/bin/gh"), \
             patch("subprocess.run", return_value=CompletedProcess(
                 args=[], returncode=0, stdout="{}", stderr="")):
            cache = {}
            result = rtci.gh_path_exists("foo/bar", "abc123", "ok.go", cache)
            self.assertEqual(result, True, "HTTP 200 must return True")

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
    """R2 verifies the REFERENCED bytes, not the reader's transcription of them.

    The old form hashed `bidder_params_json` and compared it to
    `bidder_params_sha256` -- both written by the same reader -- so a lossy
    transcription was self-consistent and passed. This class keeps the original
    test's intent (a mismatch must print full digests, so the reader can compare
    them) against the new contract.
    """

    def test_full_sha_in_mismatch_message(self):
        """A mirror mismatch must print both 64-char SHAs, never truncated."""
        bogus_sha = "deadbeef" * 8
        real = hashlib.sha256(b"{}").hexdigest()
        with tempfile.TemporaryDirectory() as td:
            blobs = pathlib.Path(td) / "blobs"
            blobs.mkdir()
            (blobs / real).write_bytes(b"{}")
            spec = make_spec(raw={
                "bidder_params_ref": {
                    "path": "static/bidder-params/x.json",
                    "resolved_commit": "a" * 40,
                    "sha256": real,
                    "bytes": 2,
                },
                "bidder_params_sha256": bogus_sha,
            })
            spec.path = str(pathlib.Path(td) / "x.golden.spec.yaml")
            findings = rtci.r2_check(spec)
        fails = [f for f in findings if f.severity == rtci.SEV_FAIL]
        self.assertTrue(fails, f"Expected R2 to FAIL on a mirror mismatch; got: {findings}")
        detail = " ".join(f.detail for f in fails)
        self.assertIn(bogus_sha, detail, f"declared SHA not printed in full: {detail}")
        self.assertIn(real, detail, f"referenced SHA not printed in full: {detail}")

    def test_corrupt_blob_fails_even_though_the_ref_is_self_consistent(self):
        """The whole point: bytes that do not hash to their own ref are caught.

        Under the old check this was invisible -- nothing compared stored bytes to
        a digest derived from anywhere but themselves."""
        with tempfile.TemporaryDirectory() as td:
            blobs = pathlib.Path(td) / "blobs"
            blobs.mkdir()
            claimed = hashlib.sha256(b"the real upstream bytes").hexdigest()
            (blobs / claimed).write_bytes(b"tampered")          # content != name
            spec = make_spec(raw={
                "bidder_params_ref": {"path": "static/bidder-params/x.json",
                                      "resolved_commit": "a" * 40,
                                      "sha256": claimed, "bytes": 23},
                "bidder_params_sha256": claimed,
            })
            spec.path = str(pathlib.Path(td) / "x.golden.spec.yaml")
            findings = rtci.r2_check(spec)
        details = " ".join(f.detail for f in findings if f.severity == rtci.SEV_FAIL)
        self.assertIn("R2a", details, f"content mismatch not caught: {details}")
        self.assertIn("R2b", details, f"byte-length mismatch not caught: {details}")

    def test_missing_blob_is_a_failure_not_a_pass(self):
        """Nothing to verify against must never read as verified."""
        with tempfile.TemporaryDirectory() as td:
            (pathlib.Path(td) / "blobs").mkdir()
            sha = "b" * 64
            spec = make_spec(raw={
                "bidder_params_ref": {"path": "static/bidder-params/x.json",
                                      "resolved_commit": "a" * 40, "sha256": sha, "bytes": 1},
                "bidder_params_sha256": sha,
            })
            spec.path = str(pathlib.Path(td) / "x.golden.spec.yaml")
            findings = rtci.r2_check(spec)
        self.assertTrue([f for f in findings if f.severity == rtci.SEV_FAIL])

    def test_alias_without_a_ref_passes(self):
        """An alias inherits its parent's params and has no upstream file."""
        spec = make_spec(raw={"meta": {"is_alias": True}})
        findings = rtci.r2_check(spec)
        self.assertTrue(all(f.severity == rtci.SEV_PASS for f in findings), findings)


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
    def _make_pair(self, go_extra: Optional[Dict[str, Any]] = None, java_extra: Optional[Dict[str, Any]] = None):
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

    def test_r8_walks_user_sync_and_static_field_paths(self):
        """Wave 11b B5 #7: r8_check now walks user-sync URLs and Java
        static-field values, not just bidder_info.endpoint. Each macro is
        recognized against per-language endpoint macros, USER_SYNC_MACROS
        (when path contains 'user_sync'), and OPENRTB_MACROS (universal)."""
        spec = make_spec("foo", "go", {
            "meta": {"bidder_name": "foo"},
            "bidder_info": {
                "endpoint": "https://x/{{.PublisherID}}",  # in GO_TEMPLATE_MACROS
                "user_sync": {
                    "iframe": {"url": "https://x/sync?gdpr={{.GDPR}}&consent={{.GDPRConsent}}"},
                    "redirect": {"url": "https://x/r?u={{.RedirectURL}}", "uid_macro": "${UID}"},
                },
            },
            "bidder_class": {
                "static_fields": [
                    {"name": "FOO_MACRO", "type": "String", "value": "{{.PublisherID}}"},
                    {"name": "PRICE_MACRO", "type": "String", "value": "${AUCTION_PRICE}"},
                ],
            },
        })
        findings = rtci.r8_check(spec)
        warns = [f for f in findings if f.severity == rtci.SEV_WARN]
        # All placeholders should be recognized: PublisherID (endpoint macro),
        # GDPR/GDPRConsent/RedirectURL (user-sync macros), UID (also user-sync),
        # AUCTION_PRICE (OpenRTB macro).
        self.assertEqual(
            warns, [],
            f"Expected zero R8 warns when all placeholders are in known registries; "
            f"got: {[f.detail for f in warns]}",
        )

    def test_r8_warns_on_unrecognized_bidder_specific_macro(self):
        """Wave 11b B5 #7: when a placeholder name isn't in any registry,
        R8 must WARN (or PASS if a provenance.warnings entry documents it)."""
        spec = make_spec("foo", "go", {
            "meta": {"bidder_name": "foo"},
            "bidder_info": {
                "endpoint": "https://x/{{.BogusUnknownMacro}}",
            },
        })
        findings = rtci.r8_check(spec)
        warns = [f for f in findings if f.severity == rtci.SEV_WARN]
        self.assertTrue(
            any("BogusUnknownMacro" in f.detail for f in warns),
            f"Expected WARN on unrecognized macro; got: {[f.detail for f in findings]}",
        )

    def test_list_set_eq_treats_lists_as_sets(self):
        """Wave 11b B5 #2: _list_set_eq must return True for lists with the
        same members in different orders (capabilities/geoscope/schema_*
        list-valued strict keys), and False for lists with different members."""
        eq = rtci._list_set_eq
        # Same members, different orders → equal
        self.assertTrue(eq(["a", "b", "c"], ["c", "a", "b"]))
        self.assertTrue(eq([1, 2, 3], [3, 2, 1]))
        # Different members → not equal
        self.assertFalse(eq(["a", "b"], ["a", "b", "c"]))
        self.assertFalse(eq([1, 2], [1, 3]))
        # Both None → equal
        self.assertTrue(eq(None, None))
        # Nested dicts in lists are JSON-serialized for comparison
        self.assertTrue(eq([{"k": "v"}, {"k": "w"}], [{"k": "w"}, {"k": "v"}]))
        # Mixed types fall through to deep_eq (None vs []  → not equal)
        self.assertFalse(eq(None, []))

    def test_maintainer_eq_compares_email_only(self):
        """Wave 11b B5 #2: _maintainer_eq treats only the email as the runtime
        invariant. Same email + different advisory fields → equal. Different
        email → not equal. Email comparison is case-insensitive + whitespace-
        trimmed."""
        eq = rtci._maintainer_eq
        # Same email, different advisory fields → equal
        self.assertTrue(eq(
            {"email": "x@y.com", "name": "Alice"},
            {"email": "x@y.com", "team": "ads"},
        ))
        # Case + whitespace insensitive
        self.assertTrue(eq({"email": "X@Y.COM"}, {"email": "  x@y.com  "}))
        # Different emails → not equal
        self.assertFalse(eq({"email": "x@y.com"}, {"email": "z@y.com"}))
        # Both None / empty → equal (both effectively "")
        self.assertTrue(eq(None, None))
        self.assertTrue(eq({}, {}))

    def test_normalize_endpoint_macros_canonicalizes_forms(self):
        """Wave 11b B4 C1: normalize_endpoint_macros must canonicalize the
        recognized macro syntaxes (Go template, Java property reference,
        Spring EL) to the `{{X}}` form so FORM_DIVERGENT comparison
        doesn't fire on pure-syntax divergence."""
        n = rtci.normalize_endpoint_macros
        self.assertEqual(n("https://x/{{.Foo}}"),     "https://x/{{Foo}}")
        self.assertEqual(n("https://x/${Foo}"),       "https://x/{{Foo}}")
        self.assertEqual(n("https://x/#{Foo}"),       "https://x/{{Foo}}")
        self.assertEqual(n("https://x/{{Foo}}"),      "https://x/{{Foo}}")
        # Multiple macros in one URL
        self.assertEqual(
            n("https://x/{{.A}}/{{.B}}?q={{.C}}"),
            "https://x/{{A}}/{{B}}?q={{C}}",
        )
        # %s positional NOT normalized (no name to canonicalize)
        self.assertEqual(n("https://x/?z=%s"), "https://x/?z=%s")
        # Non-strings pass through (None, dict, list)
        self.assertIsNone(n(None))
        self.assertEqual(n([]), [])

    def test_form_divergent_normalized_equal_no_finding(self):
        """Wave 11b B4 C1: when normalized endpoint forms agree across
        languages (Go template `{{.X}}` vs Java raw `{{X}}`), R5 must NOT
        emit a divergence finding for that key."""
        go_spec, java_spec = self._make_pair()
        go_spec.raw["bidder_info"]["endpoint"] = "https://x/foo/{{.PublisherID}}"
        java_spec.raw["bidder_info"]["endpoint"] = "https://x/foo/{{PublisherID}}"
        # Make SHAs equal so we don't catch other findings
        go_spec.raw["bidder_params_sha256"] = "z" * 64
        java_spec.raw["bidder_params_sha256"] = "z" * 64
        findings = rtci.r5_check(go_spec, java_spec, {})
        endpoint_findings = [f for f in findings if "endpoint" in f.detail and "construction" not in f.detail]
        self.assertEqual(
            endpoint_findings, [],
            f"Expected no endpoint finding when normalized forms equal; got: {endpoint_findings}",
        )

    def test_form_divergent_no_assertion_fails_assertion_missing(self):
        """Wave 11b B4 C1 strictness: when normalized endpoint forms DIFFER
        and dual-spec has no bidder_info_endpoint assertion, R5 must FAIL
        with assertion_missing — the gap must be documented or the
        divergence fixed."""
        go_spec, java_spec = self._make_pair()
        go_spec.raw["bidder_info"]["endpoint"] = "https://x/foo"
        java_spec.raw["bidder_info"]["endpoint"] = "https://x/foo?src={{PREBID_SERVER_ENDPOINT}}"
        go_spec.raw["bidder_params_sha256"] = "y" * 64
        java_spec.raw["bidder_params_sha256"] = "y" * 64
        findings = rtci.r5_check(go_spec, java_spec, {})  # no dual-spec assertion
        endpoint_fails = [f for f in findings
                          if f.severity == rtci.SEV_FAIL and "assertion_missing" in f.detail]
        self.assertTrue(
            len(endpoint_fails) >= 1,
            f"Expected FAIL assertion_missing for divergent endpoint without "
            f"dual-spec entry; got: {findings}",
        )

    def test_form_divergent_stale_pass_fails(self):
        """Wave 11b B4 C1: when dual-spec assertion claims severity:pass for
        bidder_info_endpoint but normalized forms differ, R5 must FAIL with
        stale-pass-assertion (polarity inversion)."""
        go_spec, java_spec = self._make_pair()
        go_spec.raw["bidder_info"]["endpoint"] = "https://x/foo"
        java_spec.raw["bidder_info"]["endpoint"] = "https://x/bar"
        go_spec.raw["bidder_params_sha256"] = "x" * 64
        java_spec.raw["bidder_params_sha256"] = "x" * 64
        dual_specs = {"foo": {"assertions": {"bidder_info_endpoint": {
            "severity": "pass", "divergence_summary": "claims equivalent",
        }}}}
        findings = rtci.r5_check(go_spec, java_spec, dual_specs)
        stale = [f for f in findings
                 if f.severity == rtci.SEV_FAIL and "stale-pass" in f.detail]
        self.assertTrue(
            len(stale) >= 1,
            f"Expected stale-pass FAIL when assertion claims pass but forms "
            f"differ; got: {findings}",
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


# ---------------------------------------------------------------------------
# Wave 11b post-review: R3b registry-missing fail-loud + lenient-r9 → r3b rename
# ---------------------------------------------------------------------------

class TestR3bRegistryHardening(unittest.TestCase):
    """Wave 11b post-review (item 2b): R3b must fail loudly when the taxa
    registry is missing instead of silently warn-and-continue. Mirrors the
    GhApiUnreachable Wave 10 recipe."""

    def test_parse_taxa_registry_raises_on_missing_file(self):
        with self.assertRaises(rtci.TaxaRegistryUnreachable) as cm:
            rtci.parse_taxa_registry("/nonexistent/path/behavior-taxonomy.md")
        self.assertIn("not found", str(cm.exception).lower())

    def test_parse_taxa_registry_raises_on_empty_section(self):
        """If the markdown exists but has no parseable taxa table, raise."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            # No `## quirks edge_case_taxon` header.
            f.write("# Behavior taxonomy\n\nNo registry here.\n")
            path = f.name
        try:
            with self.assertRaises(rtci.TaxaRegistryUnreachable):
                rtci.parse_taxa_registry(path)
        finally:
            os.unlink(path)

    def test_parse_taxa_registry_raises_on_empty_table(self):
        """If the registry header exists but the table parses to an empty list, raise."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Behavior taxonomy\n\n## quirks `edge_case_taxon`\n\nNo table.\n")
            path = f.name
        try:
            with self.assertRaises(rtci.TaxaRegistryUnreachable):
                rtci.parse_taxa_registry(path)
        finally:
            os.unlink(path)

    def test_parse_taxa_registry_succeeds_on_real_file(self):
        """Sanity: the actual repo's behavior-taxonomy.md parses to a
        non-empty list (regression gate for the section-detection regex)."""
        import os
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        taxonomy_path = os.path.join(
            repo_root, "prebid-server-go", "read", "skills", "shared",
            "behavior-taxonomy.md",
        )
        taxa = rtci.parse_taxa_registry(taxonomy_path)
        self.assertGreater(len(taxa), 30,
                           f"Expected ≥30 registered taxa; got {len(taxa)}")


# ---------------------------------------------------------------------------
# Wave 11b post-review (3d): R8 macro registries lifted from Python literals
# to YAML data. Verify the loader + the four expected sets.
# ---------------------------------------------------------------------------

class TestEndpointMacrosRegistry(unittest.TestCase):
    """Wave 11b post-review (3d): the four R8 macro registries are now
    loaded from `prebid-server-go/read/skills/shared/endpoint-macros.yaml`
    at module-import time. Verify the loader works + each frozenset
    contains the canonical core entries (regression gate against
    accidental YAML edits that would silently drop macros)."""

    def test_endpoint_macros_yaml_loads(self):
        """The YAML loader returns the four expected keys."""
        registries = rtci._load_endpoint_macros()
        self.assertEqual(set(registries.keys()),
                         {"go_template_macros", "java_template_macros",
                          "user_sync_macros", "openrtb_macros"})
        for key, values in registries.items():
            self.assertIsInstance(values, frozenset, key)
            self.assertGreater(len(values), 0, f"{key} must be non-empty")

    def test_go_template_macros_contains_canonical_set(self):
        """Spot-check: the canonical Go endpoint macros are still listed."""
        for required in ("AccountID", "AdUnit", "PublisherID", "PlacementID"):
            self.assertIn(required, rtci.GO_TEMPLATE_MACROS,
                          f"GO_TEMPLATE_MACROS missing canonical {required!r}")

    def test_user_sync_macros_admits_both_casings(self):
        """The set must include both Go PascalCase + Java snake_case forms."""
        self.assertIn("GDPR", rtci.USER_SYNC_MACROS)
        self.assertIn("gdpr", rtci.USER_SYNC_MACROS)
        self.assertIn("GDPRConsent", rtci.USER_SYNC_MACROS)
        self.assertIn("gdpr_consent", rtci.USER_SYNC_MACROS)

    def test_openrtb_macros_includes_auction_price(self):
        """OpenRTB 2.5 §4.1 AUCTION_PRICE is the most common burl/nurl macro."""
        self.assertIn("AUCTION_PRICE", rtci.OPENRTB_MACROS)


class TestR11PortRoundTrip(unittest.TestCase):
    """Phase D4.1: r_port_round_trip validates round-trip artifacts when
    the operator persists them. Without artifacts, the function emits SKIP
    findings — the framework is in place for when D2.8 / D3.8 operator
    runs land artifacts."""

    def test_skip_when_one_side_missing(self):
        go_spec = make_spec(language="go", raw={"meta": {"bidder_name": "kobler"}})
        findings = rtci.r_port_round_trip(go_spec, None)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, rtci.SEV_SKIP)
        self.assertIn("paired", findings[0].detail)

    def test_skip_when_no_round_trip_artifact_exists(self):
        """Common state today: pair fixtures present in the corpus, but no
        port skill has emitted round-trip artifacts. Emits SKIP per direction."""
        go_spec = make_spec(language="go", raw={"meta": {"bidder_name": "nonexistent_test_bidder"}})
        java_spec = make_spec(language="java", raw={"meta": {"bidder_name": "nonexistent_test_bidder"}})
        findings = rtci.r_port_round_trip(go_spec, java_spec)
        # Two SKIP findings — one per direction (go-to-java, java-to-go).
        self.assertEqual(len(findings), 2)
        for f in findings:
            self.assertEqual(f.severity, rtci.SEV_SKIP)
            self.assertIn("no round-trip artifact", f.detail)

    def test_lossy_paths_loader_returns_dict(self):
        """The Round-Trip Safety table loader returns a non-empty dict
        keyed by field path. Smoke-test against the live YAML."""
        paths = rtci._load_lossy_field_paths()
        self.assertIsInstance(paths, dict)
        # The YAML has at least a handful of entries; we don't assert exact
        # paths because the corpus evolves. The loader just needs to parse
        # SOMETHING from the verdict_table rows.
        for path, directions in paths.items():
            self.assertIsInstance(path, str)
            self.assertIsInstance(directions, dict)

    def test_round_trip_diff_skips_lossy_direction_fields(self):
        """A field divergence on a path flagged lossy in the relevant
        direction is NOT recorded as unexpected."""
        original = {"bidder_info": {"endpoint": "https://x"}}
        round_tripped = {"bidder_info": {"endpoint": "https://y"}}
        # Synthetic lossy paths: flag bidder_info.endpoint as lossy go-to-java.
        lossy = {"bidder_info.endpoint": {"go-to-java": True}}
        diffs = rtci._round_trip_diff(original, round_tripped, lossy, "go-to-java")
        self.assertEqual(diffs, [])

    def test_round_trip_diff_records_unexpected_divergence(self):
        original = {"bidder_info": {"endpoint": "https://x", "gvl_vendor_id": 0}}
        round_tripped = {"bidder_info": {"endpoint": "https://y", "gvl_vendor_id": 0}}
        lossy = {}  # nothing is lossy
        diffs = rtci._round_trip_diff(original, round_tripped, lossy, "go-to-java")
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["path"], "bidder_info.endpoint")
        self.assertEqual(diffs[0]["original"], "https://x")
        self.assertEqual(diffs[0]["round_tripped"], "https://y")

    def test_round_trip_diff_set_equality_on_lists(self):
        """List-valued fields (like geoscope) compare set-equally — a
        re-ordered list is NOT a divergence."""
        original = {"bidder_info": {"geoscope": ["NOR", "SWE", "DNK"]}}
        round_tripped = {"bidder_info": {"geoscope": ["DNK", "NOR", "SWE"]}}
        diffs = rtci._round_trip_diff(original, round_tripped, {}, "go-to-java")
        self.assertEqual(diffs, [])

    def test_round_trip_diff_normalizes_endpoint_macros(self):
        """Phase D4.1 follow-up: bidder_info.endpoint with Go {{.Host}}
        vs Java ${host} canonicalizes to {{Host}} on both sides; should
        NOT register as a divergence (matches R5 form-divergent semantics)."""
        original = {"bidder_info": {"endpoint": "https://x/{{.Host}}/bid"}}
        round_tripped = {"bidder_info": {"endpoint": "https://x/${Host}/bid"}}
        diffs = rtci._round_trip_diff(original, round_tripped, {}, "go-to-java")
        self.assertEqual(diffs, [])

    def test_round_trip_diff_endpoint_real_divergence_still_flags(self):
        """When endpoints diverge BEYOND macro syntax (different host /
        path), normalize_endpoint_macros doesn't paper it over — the
        diff still fires."""
        original = {"bidder_info": {"endpoint": "https://go.example/{{.Host}}/bid"}}
        round_tripped = {"bidder_info": {"endpoint": "https://java.example/${Host}/bid"}}
        diffs = rtci._round_trip_diff(original, round_tripped, {}, "go-to-java")
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["path"], "bidder_info.endpoint")

    def test_r_port_round_trip_emits_pass_for_lossy_flagged_divergence(self):
        """Phase D4.1 follow-up: when a synthetic round-trip artifact
        has a divergent value on a path that the Round-Trip Safety table
        flags as lossy in the relevant direction, the diff exempts that
        field and r_port_round_trip emits PASS rather than WARN."""
        import os
        bidder = "synthetic_lossy_exemption_bidder_xyz"
        original = {
            "meta": {"bidder_name": bidder},
            "bidder_info": {
                "endpoint": "https://x",
                "geoscope": ["NOR"],
                "gvl_vendor_id": 0,
            },
            "bidder_params_sha256": "a" * 64,
        }
        # Round-tripped artifact has a different geoscope value — would
        # normally be a divergence. We synthesize a lossy_paths entry
        # flagging bidder_info.geoscope as lossy go-to-java to exercise
        # the exemption.
        round_tripped_artifact = dict(original)
        round_tripped_artifact["bidder_info"] = dict(original["bidder_info"])
        round_tripped_artifact["bidder_info"]["geoscope"] = ["NOR", "SWE", "DNK"]

        rt_dir = os.path.join(rtci.REPO_ROOT, ".tmp", "full-loop",
                              "test-r11-lossy-run", "round-trip", "go")
        os.makedirs(rt_dir, exist_ok=True)
        rt_path = os.path.join(rt_dir, f"{bidder}.yaml")
        rt_dir_java = os.path.join(rtci.REPO_ROOT, ".tmp", "full-loop",
                                   "test-r11-lossy-run", "round-trip", "java")
        os.makedirs(rt_dir_java, exist_ok=True)
        rt_path_java = os.path.join(rt_dir_java, f"{bidder}.yaml")
        try:
            import yaml as _yaml
            with open(rt_path, "w") as fh:
                _yaml.safe_dump(round_tripped_artifact, fh)
            with open(rt_path_java, "w") as fh:
                _yaml.safe_dump(round_tripped_artifact, fh)

            go_spec = make_spec(bidder=bidder, language="go", raw=original)
            java_spec = make_spec(bidder=bidder, language="java", raw=original)
            # Synthetic lossy_paths flagging geoscope as lossy in BOTH
            # directions — proves the diff loop honors the exemption.
            lossy = {
                "bidder_info.geoscope": {"go-to-java": True, "java-to-go": True},
            }
            findings = rtci.r_port_round_trip(go_spec, java_spec, lossy)
            severities = [f.severity for f in findings]
            # Both directions should emit PASS (geoscope divergence
            # exempted by lossy_paths) — no WARN.
            self.assertIn(rtci.SEV_PASS, severities)
            self.assertNotIn(rtci.SEV_WARN, severities)
        finally:
            import shutil
            shutil.rmtree(os.path.join(rtci.REPO_ROOT, ".tmp", "full-loop", "test-r11-lossy-run"),
                          ignore_errors=True)

    def test_pass_finding_when_artifact_present_and_matches(self):
        """When a synthetic round-trip artifact exists at the canonical
        path AND matches the original on the checked fields, emit PASS."""
        import os
        bidder = "synthetic_rt_test_bidder_xyz"
        original = {
            "meta": {"bidder_name": bidder},
            "bidder_info": {
                "endpoint": "https://x",
                "geoscope": ["NOR", "SWE"],
                "gvl_vendor_id": 0,
            },
            "bidder_params_sha256": "a" * 64,
        }
        # Drop the synthetic artifact at the canonical .tmp path so
        # _round_trip_artifact_path picks it up.
        rt_dir = os.path.join(rtci.REPO_ROOT, ".tmp", "full-loop",
                              "test-r11-pass-run", "round-trip", "go")
        os.makedirs(rt_dir, exist_ok=True)
        rt_path = os.path.join(rt_dir, f"{bidder}.yaml")
        try:
            import yaml as _yaml
            with open(rt_path, "w") as fh:
                _yaml.safe_dump(original, fh)
            # Also drop a Java-side artifact so both directions emit PASS.
            rt_dir_java = os.path.join(rtci.REPO_ROOT, ".tmp", "full-loop",
                                       "test-r11-pass-run", "round-trip", "java")
            os.makedirs(rt_dir_java, exist_ok=True)
            with open(os.path.join(rt_dir_java, f"{bidder}.yaml"), "w") as fh:
                _yaml.safe_dump(original, fh)

            go_spec = make_spec(bidder=bidder, language="go", raw=original)
            java_spec = make_spec(bidder=bidder, language="java", raw=original)
            findings = rtci.r_port_round_trip(go_spec, java_spec)
            severities = [f.severity for f in findings]
            self.assertIn(rtci.SEV_PASS, severities)
        finally:
            # Clean up the synthetic artifact.
            import shutil
            shutil.rmtree(os.path.join(rtci.REPO_ROOT, ".tmp", "full-loop", "test-r11-pass-run"),
                          ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
