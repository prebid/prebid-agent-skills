#!/usr/bin/env python3
"""Unit tests for scripts/lib/port_engine.py.

Lib-level tests covering each of the nine mechanical helpers. External
dependencies (filesystem, subprocess, upstream) are exercised via
dependency-injection hooks where helpers expose them; otherwise tests
use ``tmp_path``-style temporary fixtures so the suite remains
hermetic.

Run from repo root:
    python3 -m pytest scripts/tests/test_port_engine.py
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Tuple

from scripts.lib.port_engine import (
    DEFAULT_NAME_ALLOW_LIST,
    alias_graph_invert,
    alphabetical_insert,
    byte_copy,
    gofmt_post_process,
    iab_table_translate,
    normalize_bidder_name,
    port_report_emit,
    prefix_uniqueness_check,
    r5_check_at_port_time,
)


# ---------------------------------------------------------------------------
# Helper 1: byte_copy
# ---------------------------------------------------------------------------


class TestByteCopy(unittest.TestCase):
    def test_copies_bytes_verbatim(self):
        with TemporaryDirectory() as td:
            src = Path(td) / "src.json"
            dst = Path(td) / "dst.json"
            payload = b'{"required":["a","b"],"properties":{"a":{"type":"string"}}}\n'
            src.write_bytes(payload)
            ok = byte_copy(src, dst)
            self.assertTrue(ok)
            self.assertEqual(dst.read_bytes(), payload)

    def test_creates_parent_dirs(self):
        with TemporaryDirectory() as td:
            src = Path(td) / "src.txt"
            src.write_bytes(b"x")
            dst = Path(td) / "deep" / "nested" / "dst.txt"
            ok = byte_copy(src, dst)
            self.assertTrue(ok)
            self.assertEqual(dst.read_bytes(), b"x")

    def test_empty_file_copies_cleanly(self):
        with TemporaryDirectory() as td:
            src = Path(td) / "empty.json"
            dst = Path(td) / "empty-out.json"
            src.write_bytes(b"")
            ok = byte_copy(src, dst)
            self.assertTrue(ok)
            self.assertEqual(dst.read_bytes(), b"")


# ---------------------------------------------------------------------------
# Helper 2: normalize_bidder_name (Rule 46)
# ---------------------------------------------------------------------------


class TestNormalizeBidderName(unittest.TestCase):
    def test_lowercase_passthrough(self):
        self.assertEqual(normalize_bidder_name("kobler"), "kobler")

    def test_camel_case_drops_to_lowercase(self):
        self.assertEqual(normalize_bidder_name("adkernelAdn"), "adkerneladn")

    def test_underscore_dropped(self):
        self.assertEqual(normalize_bidder_name("cadent_aperture_mx"), "emxdigital")  # explicit allow-list rebrand
        self.assertEqual(normalize_bidder_name("lm_kiviads"), "lmkiviads")

    def test_hyphen_dropped(self):
        self.assertEqual(normalize_bidder_name("freewheel-ssp"), "freewheelssp")

    def test_digit_leading_passes_through(self):
        self.assertEqual(normalize_bidder_name("33across"), "33across")
        self.assertEqual(normalize_bidder_name("152media"), "152media")

    def test_custom_allow_list_overrides_default(self):
        self.assertEqual(
            normalize_bidder_name("kobler", allow_list={"kobler": "KoblerOverride"}),
            "KoblerOverride",
        )

    def test_target_lang_java_only(self):
        with self.assertRaises(ValueError):
            normalize_bidder_name("kobler", target_lang="go")


# ---------------------------------------------------------------------------
# Helper 3: alias_graph_invert (Rule 33)
# ---------------------------------------------------------------------------


class TestAliasGraphInvert(unittest.TestCase):
    def test_go_to_java_emits_diverging_overrides_only(self):
        parent = {
            "meta": {"bidder_name": "smarthub"},
            "bidder_info": {
                "endpoint": "https://example.com/bid",
                "geoscope": ["US", "EU"],
                "capabilities": {"site": {"mediaTypes": ["banner"]}},
            },
        }
        alias_a = {
            "meta": {"bidder_name": "host_a"},
            "bidder_info": {
                "endpoint": "https://host-a.example.com/bid",
                "geoscope": ["US", "EU"],
                "capabilities": {"site": {"mediaTypes": ["banner"]}},
            },
        }
        alias_b = {
            "meta": {"bidder_name": "host_b"},
            "bidder_info": {
                "endpoint": "https://host-b.example.com/bid",
                "geoscope": ["KR"],
                "capabilities": {"site": {"mediaTypes": ["banner"]}},
            },
        }
        result = alias_graph_invert(parent, [alias_a, alias_b], direction="go-to-java")
        self.assertEqual(set(result.keys()), {"host_a", "host_b"})
        # alias_a only diverges on endpoint (geoscope + capabilities match parent).
        self.assertEqual(result["host_a"], {"endpoint": "https://host-a.example.com/bid"})
        # alias_b diverges on endpoint + geoscope.
        self.assertEqual(set(result["host_b"].keys()), {"endpoint", "geoscope"})

    def test_java_to_go_emits_per_alias_yaml_with_aliasOf(self):
        parent = {
            "meta": {"bidder_name": "adkernel"},
            "bidder_info": {
                "endpoint": "https://example.com/{{Host}}/bid",
                "geoscope": ["US"],
            },
            "aliases": {
                "adkernel_eu": {"endpoint": "https://eu.example.com/{{Host}}/bid"},
                "adkernel_kr": {"geoscope": ["KR"]},
            },
        }
        result = alias_graph_invert(parent, [], direction="java-to-go")
        self.assertEqual(set(result.keys()), {"adkernel_eu", "adkernel_kr"})
        self.assertEqual(result["adkernel_eu"]["aliasOf"], "adkernel")
        # adkernel_eu inherits parent's geoscope, overrides endpoint.
        self.assertEqual(result["adkernel_eu"]["endpoint"], "https://eu.example.com/{{Host}}/bid")
        self.assertEqual(result["adkernel_eu"]["geoscope"], ["US"])
        # adkernel_kr inherits parent's endpoint, overrides geoscope.
        self.assertEqual(result["adkernel_kr"]["geoscope"], ["KR"])
        self.assertEqual(result["adkernel_kr"]["endpoint"], "https://example.com/{{Host}}/bid")

    def test_unsupported_direction_raises(self):
        with self.assertRaises(ValueError):
            alias_graph_invert({}, [], direction="bidirectional")


# ---------------------------------------------------------------------------
# Helper 4: iab_table_translate (Rule 42)
# ---------------------------------------------------------------------------


class TestIabTableTranslate(unittest.TestCase):
    def test_go_to_java_extracts_map(self):
        go_source = '''package iab

var iabCategories = map[string]string{
    "IAB1": "Arts & Entertainment",
    "IAB2-1": "Auto Parts",
    "IAB3": "Business",
}
'''
        result = iab_table_translate("go-to-java", go_source)
        self.assertEqual(result, {
            "IAB1": "Arts & Entertainment",
            "IAB2-1": "Auto Parts",
            "IAB3": "Business",
        })

    def test_java_to_go_emits_sorted_data_file(self):
        java_dict = {
            "IAB3": "Business",
            "IAB1": "Arts & Entertainment",
            "IAB2-1": "Auto Parts",
        }
        go_source = iab_table_translate("java-to-go", java_dict)
        # Result should be valid Go source; entries sorted alphabetically by key.
        self.assertIn("var iabCategories = map[string]string{", go_source)
        self.assertIn('"IAB1": "Arts & Entertainment",', go_source)
        # IAB1 should appear before IAB2-1 (alphabetical sort).
        idx_iab1 = go_source.index('"IAB1"')
        idx_iab2 = go_source.index('"IAB2-1"')
        self.assertLess(idx_iab1, idx_iab2)

    def test_round_trip_preserves_mapping(self):
        original = {"IAB1": "Arts", "IAB2": "Cars"}
        go_source = iab_table_translate("java-to-go", original)
        round_tripped = iab_table_translate("go-to-java", go_source)
        self.assertEqual(round_tripped, original)

    def test_invalid_direction_raises(self):
        with self.assertRaises(ValueError):
            iab_table_translate("inverse", "")

    def test_type_mismatch_raises(self):
        with self.assertRaises(TypeError):
            iab_table_translate("go-to-java", {"IAB1": "x"})  # dict where string expected
        with self.assertRaises(TypeError):
            iab_table_translate("java-to-go", "string")  # string where dict expected


# ---------------------------------------------------------------------------
# Helper 5: r5_check_at_port_time
# ---------------------------------------------------------------------------


class TestR5CheckAtPortTime(unittest.TestCase):
    def test_pass_state_for_byte_equal_specs(self):
        sha = "0" * 64
        source = {
            "source_language": "go",
            "meta": {"bidder_name": "kobler"},
            "bidder_params_sha256": sha,
        }
        dest = {
            "source_language": "java",
            "meta": {"bidder_name": "kobler"},
            "bidder_params_sha256": sha,
        }
        result = r5_check_at_port_time(source, dest)
        self.assertEqual(result.state, "pass")

    def test_routes_go_to_java_correctly(self):
        # Verify that compare_pair receives the Go spec as go_view (first arg).
        go_source = {
            "source_language": "go",
            "meta": {"bidder_name": "kobler"},
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"capabilities": {"site": {"mediaTypes": ["banner"]}}},
        }
        java_dest = {
            "source_language": "java",
            "meta": {"bidder_name": "kobler"},
            "bidder_params_sha256": "a" * 64,
            "bidder_info": {"capabilities": {"app": {"mediaTypes": ["video"]}}},
        }
        result = r5_check_at_port_time(go_source, java_dest)
        # Diverging capabilities surfaces as fail-semantic.
        self.assertEqual(result.state, "fail-semantic-divergence")

    def test_unsupported_pair_raises(self):
        source = {"source_language": "go", "meta": {"bidder_name": "x"}}
        dest = {"source_language": "go", "meta": {"bidder_name": "x"}}
        with self.assertRaises(ValueError):
            r5_check_at_port_time(source, dest)


# ---------------------------------------------------------------------------
# Helper 6: port_report_emit
# ---------------------------------------------------------------------------


class TestPortReportEmit(unittest.TestCase):
    def _minimal_report(self) -> Dict[str, Any]:
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

    def test_valid_report_writes_to_path(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "port-report.json"
            port_report_emit(self._minimal_report(), path)
            self.assertTrue(path.exists())
            written = json.loads(path.read_text())
            self.assertEqual(written["port_report_version"], "0.2.0")

    def test_invalid_report_raises(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "port-report.json"
            invalid = self._minimal_report()
            invalid["r5_check"]["state"] = "bogus-state"
            try:
                import jsonschema
            except ImportError:  # pragma: no cover
                self.skipTest("jsonschema not installed")
            with self.assertRaises(jsonschema.ValidationError):
                port_report_emit(invalid, path)

    def test_creates_parent_dirs(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "deep" / "nested" / "port-report.json"
            port_report_emit(self._minimal_report(), path)
            self.assertTrue(path.exists())


# ---------------------------------------------------------------------------
# Helper 7: alphabetical_insert
# ---------------------------------------------------------------------------


class TestAlphabeticalInsert(unittest.TestCase):
    def test_inserts_at_correct_alpha_position(self):
        with TemporaryDirectory() as td:
            fp = Path(td) / "bidders.go"
            fp.write_text(
                "package openrtb_ext\n"
                "\n"
                "const (\n"
                "    BidderAax    BidderName = \"aax\"\n"
                "    BidderAdverxo BidderName = \"adverxo\"\n"
                "    BidderKobler BidderName = \"kobler\"\n"
                ")\n"
            )
            alphabetical_insert(
                fp,
                marker_pattern=r"BidderName = \".*\"",
                insert_line='    BidderAdkernel BidderName = "adkernel"',
            )
            text = fp.read_text()
            lines = text.splitlines()
            # BidderAdkernel should appear between BidderAax and BidderAdverxo.
            idx_aax = next(i for i, ln in enumerate(lines) if "BidderAax " in ln)
            idx_adk = next(i for i, ln in enumerate(lines) if "BidderAdkernel " in ln)
            idx_adv = next(i for i, ln in enumerate(lines) if "BidderAdverxo " in ln)
            self.assertLess(idx_aax, idx_adk)
            self.assertLess(idx_adk, idx_adv)

    def test_idempotent_on_existing_line(self):
        with TemporaryDirectory() as td:
            fp = Path(td) / "bidders.go"
            initial = (
                "const (\n"
                "    BidderAax    BidderName = \"aax\"\n"
                "    BidderKobler BidderName = \"kobler\"\n"
                ")\n"
            )
            fp.write_text(initial)
            insert = '    BidderAax    BidderName = "aax"'
            alphabetical_insert(fp, r"BidderName = \".*\"", insert)
            # File unchanged (modulo possibly normalized trailing newline).
            self.assertEqual(fp.read_text().count("BidderAax"), 1)

    def test_no_marker_match_raises(self):
        with TemporaryDirectory() as td:
            fp = Path(td) / "bidders.go"
            fp.write_text("package openrtb_ext\n")
            with self.assertRaises(ValueError):
                alphabetical_insert(fp, r"BidderName = ", "    NewLine")


# ---------------------------------------------------------------------------
# Helper 8: prefix_uniqueness_check
# ---------------------------------------------------------------------------


class TestPrefixUniquenessCheck(unittest.TestCase):
    def test_no_collision_returns_ok(self):
        existing = ["aax", "adkernel", "kobler", "vungle"]
        ok, colliding = prefix_uniqueness_check("go", "thetradedesk", existing_names=existing)
        self.assertTrue(ok)
        self.assertEqual(colliding, [])

    def test_collision_with_first_six_letters_caught(self):
        existing = ["adkernel", "kobler"]
        # "adkernelAdn" shares 'adkern' prefix with "adkernel".
        ok, colliding = prefix_uniqueness_check("go", "adkernelAdn", existing_names=existing)
        self.assertFalse(ok)
        self.assertEqual(colliding, ["adkernel"])

    def test_six_or_more_letter_names_with_same_prefix_collide(self):
        # adkernelAdn and adkernel share 'adkern' first-6 prefix → collision.
        # adkernelEU and adverxo share 'a' but diverge at 'dk' vs 'dv' → no collision.
        existing = ["adkernelAdn", "adverxo", "vungle"]
        ok, colliding = prefix_uniqueness_check("go", "adkernelEU", existing_names=existing)
        self.assertFalse(ok)
        self.assertEqual(colliding, ["adkernelAdn"])

    def test_java_target_returns_ok_unconditionally(self):
        # Java has no first-6-letter gatekeeper.
        ok, colliding = prefix_uniqueness_check(
            "java", "adkernelAdn", existing_names=["adkernel"]
        )
        self.assertTrue(ok)
        self.assertEqual(colliding, [])

    def test_unsupported_target_lang_raises(self):
        with self.assertRaises(ValueError):
            prefix_uniqueness_check("python", "kobler", existing_names=[])

    def test_missing_table_returns_best_effort_ok(self):
        # Neither existing_names nor a real table_path → best-effort True.
        with TemporaryDirectory() as td:
            ok, colliding = prefix_uniqueness_check(
                "go", "kobler",
                table_path=Path(td) / "nonexistent.yaml",
            )
            self.assertTrue(ok)
            self.assertEqual(colliding, [])


# ---------------------------------------------------------------------------
# Helper 9: gofmt_post_process
# ---------------------------------------------------------------------------


class TestGofmtPostProcess(unittest.TestCase):
    def test_empty_paths_returns_ok(self):
        ok, msg = gofmt_post_process([])
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_runner_hook_called_with_argv(self):
        captured: List[List[str]] = []

        def fake_runner(argv: List[str]) -> Tuple[int, str, str]:
            captured.append(argv)
            return 0, "", ""

        ok, msg = gofmt_post_process(["a.go", "b.go"], runner=fake_runner)
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        self.assertEqual(captured, [["gofmt", "-s", "-w", "a.go", "b.go"]])

    def test_nonzero_exit_propagates_stderr(self):
        def fake_runner(_argv: List[str]) -> Tuple[int, str, str]:
            return 1, "", "error: bad syntax"

        ok, msg = gofmt_post_process(["a.go"], runner=fake_runner)
        self.assertFalse(ok)
        self.assertEqual(msg, "error: bad syntax")


# ---------------------------------------------------------------------------
# Allow-list constant
# ---------------------------------------------------------------------------


class TestDefaultAllowList(unittest.TestCase):
    def test_known_rebrand_present(self):
        self.assertEqual(DEFAULT_NAME_ALLOW_LIST.get("cadent_aperture_mx"), "emxdigital")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
