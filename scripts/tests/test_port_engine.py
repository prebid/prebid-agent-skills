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
    TEST_ENDPOINT,
    alias_graph_invert,
    alphabetical_insert,
    byte_copy,
    exemplary_fixture_assemble_java_to_go,
    gofmt_post_process,
    iab_table_translate,
    imp_ext_shape_transform_java_to_go,
    normalize_bidder_name,
    port_report_emit,
    prefix_uniqueness_check,
    r5_check_at_port_time,
    simulate_makerequests_mutations,
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

    def test_maintainer_override_propagates(self):
        """Per R5-strict (post-Wave-11b _maintainer_eq), maintainer email is the
        runtime invariant; an alias may legitimately override it. The helper
        forwards the override rather than silently dropping it."""
        parent = {
            "meta": {"bidder_name": "smarthub"},
            "bidder_info": {
                "endpoint": "https://example.com/bid",
                "maintainer": {"email": "support@smarthub.com"},
            },
        }
        alias = {
            "meta": {"bidder_name": "smarthub_eu"},
            "bidder_info": {
                "endpoint": "https://example.com/bid",
                "maintainer": {"email": "eu-support@smarthub.com"},
            },
        }
        result = alias_graph_invert(parent, [alias], direction="go-to-java")
        self.assertIn("maintainer", result["smarthub_eu"])
        self.assertEqual(
            result["smarthub_eu"]["maintainer"],
            {"email": "eu-support@smarthub.com"},
        )

    def test_schema_interpretation_keys_NOT_aliasable(self):
        """params.schema_interpretation.* fields are tied to bidder-params
        identity; aliases inherit by reference and CANNOT override them.
        The helper does NOT forward these keys even if a malformed alias
        spec carries them."""
        parent = {
            "meta": {"bidder_name": "kobler"},
            "bidder_info": {"endpoint": "https://example.com/bid"},
        }
        alias = {
            "meta": {"bidder_name": "kobler_alt"},
            "bidder_info": {
                "endpoint": "https://example.com/bid",
                # Malformed: alias attempting schema_interpretation override.
                # (Not a valid R5 case but worth guarding against.)
            },
            "params": {
                "schema_interpretation": {"required_fields": ["x", "y"]},
            },
        }
        result = alias_graph_invert(parent, [alias], direction="go-to-java")
        self.assertNotIn("schema_interpretation", result["kobler_alt"])
        self.assertNotIn("required_fields", result["kobler_alt"])


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

    def test_brace_inside_string_value_does_not_close_map(self):
        """A literal '}' inside a Go string value must not be parsed as the
        map's closing brace."""
        go_source = '''package iab

var iabCategories = map[string]string{
    "IAB1": "Arts {with brace}",
    "IAB2": "Cars",
}
'''
        result = iab_table_translate("go-to-java", go_source)
        self.assertEqual(result, {
            "IAB1": "Arts {with brace}",
            "IAB2": "Cars",
        })

    def test_escaped_quote_inside_value_handled(self):
        """A backslash-escaped quote inside a value must parse correctly."""
        # Use a raw string to construct: "IAB1": "Has \"escaped\" quotes",
        go_source = (
            'package iab\n\n'
            'var iabCategories = map[string]string{\n'
            '    "IAB1": "Has \\"escaped\\" quotes",\n'
            '    "IAB2": "Plain",\n'
            '}\n'
        )
        result = iab_table_translate("go-to-java", go_source)
        self.assertEqual(result["IAB1"], 'Has "escaped" quotes')
        self.assertEqual(result["IAB2"], "Plain")

    def test_custom_package_and_var_name_in_emit(self):
        """java-to-go honors package_name and var_name kwargs."""
        result = iab_table_translate(
            "java-to-go",
            {"IAB1": "Arts"},
            package_name="customiab",
            var_name="categoryMap",
        )
        self.assertIn("package customiab", result)
        self.assertIn("var categoryMap = map[string]string{", result)

    def test_non_default_var_name_parses_back(self):
        """Parser accepts any var name matching the *iab* pattern (case-insensitive)."""
        go_source = '''package custom

var bidderIabCategoryTable = map[string]string{
    "IAB1": "Arts",
}
'''
        result = iab_table_translate("go-to-java", go_source)
        self.assertEqual(result, {"IAB1": "Arts"})


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

    def test_picks_longest_run_when_pattern_matches_two_blocks(self):
        """Two const blocks share the marker pattern; helper picks the
        longer (the actual bidder block) and leaves the smaller (reserved)
        alone."""
        with TemporaryDirectory() as td:
            fp = Path(td) / "bidders.go"
            fp.write_text(
                "package openrtb_ext\n"
                "\n"
                "const (\n"
                '    BidderReservedAll BidderName = "all"\n'
                '    BidderReservedData BidderName = "data"\n'
                ")\n"
                "\n"
                "const (\n"
                '    BidderAax       BidderName = "aax"\n'
                '    BidderAdkernel  BidderName = "adkernel"\n'
                '    BidderAdverxo   BidderName = "adverxo"\n'
                '    BidderKobler    BidderName = "kobler"\n'
                ")\n"
            )
            alphabetical_insert(
                fp,
                marker_pattern=r'Bidder\w+\s+BidderName\s*=',
                insert_line='    BidderEdge226   BidderName = "edge226"',
            )
            text = fp.read_text()
            lines = text.splitlines()
            # Reserved block stays untouched (only 2 entries).
            reserved_lines = [ln for ln in lines if "BidderReserved" in ln]
            self.assertEqual(len(reserved_lines), 2)
            # New entry lands between BidderAdverxo and BidderKobler.
            idx_adv = next(i for i, ln in enumerate(lines) if "BidderAdverxo " in ln)
            idx_edge = next(i for i, ln in enumerate(lines) if "BidderEdge226" in ln)
            idx_kob = next(i for i, ln in enumerate(lines) if "BidderKobler " in ln)
            self.assertLess(idx_adv, idx_edge)
            self.assertLess(idx_edge, idx_kob)

    def test_preserves_existing_local_violations(self):
        """Upstream HEAD has ~20 entries locally out-of-order vs (lower, s);
        helper must NOT re-sort the existing block, only insert at the
        canonical position for the new entry."""
        with TemporaryDirectory() as td:
            fp = Path(td) / "bidders.go"
            # Deliberately swap two entries (BidderAdtelligent / BidderAdtrgtme)
            # to mimic the real upstream local violation.
            fp.write_text(
                "package openrtb_ext\n"
                "\n"
                "const (\n"
                '    BidderAax        BidderName = "aax"\n'
                '    BidderAdtrgtme   BidderName = "adtrgtme"\n'  # out of order
                '    BidderAdtelligent BidderName = "adtelligent"\n'  # belongs before adtrgtme
                '    BidderKobler     BidderName = "kobler"\n'
                ")\n"
            )
            alphabetical_insert(
                fp,
                marker_pattern=r'Bidder\w+\s+BidderName\s*=',
                insert_line='    BidderVungle     BidderName = "vungle"',
            )
            text = fp.read_text()
            lines = text.splitlines()
            # The existing local violation MUST be preserved.
            adtrgtme_idx = next(i for i, ln in enumerate(lines) if "BidderAdtrgtme " in ln)
            adtellig_idx = next(i for i, ln in enumerate(lines) if "BidderAdtelligent " in ln)
            self.assertLess(adtrgtme_idx, adtellig_idx,
                            "helper must preserve existing local violations; not re-sort")
            # New entry lands at correct (lower, s) position (after kobler).
            kob_idx = next(i for i, ln in enumerate(lines) if "BidderKobler " in ln)
            vungle_idx = next(i for i, ln in enumerate(lines) if "BidderVungle " in ln)
            self.assertLess(kob_idx, vungle_idx)

    def test_tie_among_longest_runs_raises(self):
        """If two contiguous runs are equal length, helper refuses to guess."""
        with TemporaryDirectory() as td:
            fp = Path(td) / "ambiguous.go"
            fp.write_text(
                "const (\n"
                '    A BidderName = "a"\n'
                '    B BidderName = "b"\n'
                ")\n"
                "\n"
                "const (\n"
                '    C BidderName = "c"\n'
                '    D BidderName = "d"\n'
                ")\n"
            )
            with self.assertRaises(ValueError):
                alphabetical_insert(
                    fp,
                    marker_pattern=r'BidderName\s*=',
                    insert_line='    E BidderName = "e"',
                )


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


class TestMvnCheckstyleDryRun(unittest.TestCase):
    """Phase D4.3: mvn_checkstyle_dry_run helper exercises checkstyle:check
    against the operator's local prebid-server-java clone before the port PR
    is submitted. Tests use the runner DI hook so they're hermetic."""

    def test_target_clone_missing_returns_infrastructure_error(self):
        from scripts.lib.port_engine import mvn_checkstyle_dry_run
        ok, violations = mvn_checkstyle_dry_run("/nonexistent/path/here")
        self.assertFalse(ok)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["severity"], "infrastructure")
        self.assertIn("not a directory", violations[0]["message"])

    def test_clean_run_returns_ok_no_violations(self):
        from scripts.lib.port_engine import mvn_checkstyle_dry_run
        with TemporaryDirectory() as td:
            captured = []

            def fake_runner(argv, cwd):
                captured.append((argv, str(cwd)))
                return 0, "[INFO] BUILD SUCCESS\n", ""

            ok, violations = mvn_checkstyle_dry_run(td, runner=fake_runner)
            self.assertTrue(ok)
            self.assertEqual(violations, [])
            argv, cwd = captured[0]
            self.assertEqual(argv[:3], ["mvn", "-B", "checkstyle:check"])
            self.assertEqual(cwd, td)

    def test_violations_parsed_from_stdout(self):
        from scripts.lib.port_engine import mvn_checkstyle_dry_run
        sample_stdout = (
            "[INFO] Some banner line\n"
            "[ERROR] /clone/src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java:42:5: "
            "Method length is 200 lines (max allowed is 150). [MethodLength]\n"
            "[WARN] /clone/src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java:88:1: "
            "Line is 130 chars (max 120). [LineLength]\n"
            "[INFO] BUILD FAILURE\n"
        )
        with TemporaryDirectory() as td:
            ok, violations = mvn_checkstyle_dry_run(
                td,
                runner=lambda _argv, _cwd: (1, sample_stdout, ""),
            )
            self.assertFalse(ok)
            self.assertEqual(len(violations), 2)
            self.assertEqual(violations[0]["severity"], "error")
            self.assertEqual(violations[0]["line"], 42)
            self.assertEqual(violations[0]["column"], 5)
            self.assertEqual(violations[0]["rule"], "MethodLength")
            self.assertIn("KoblerBidder.java", violations[0]["file"])
            self.assertEqual(violations[1]["severity"], "warn")
            self.assertEqual(violations[1]["line"], 88)
            self.assertEqual(violations[1]["rule"], "LineLength")

    def test_violations_parsed_from_mvn_3x_default_format(self):
        """Phase D4.3 follow-up: maven-checkstyle-plugin 3.x default format
        is `[SEV] /path/Foo.java:[LINE,COL] (group) Rule: msg`. The earlier
        format-A-only regex parsed zero violations against a real run."""
        from scripts.lib.port_engine import mvn_checkstyle_dry_run
        sample_stdout = (
            "[INFO] Running checkstyle:check\n"
            "[ERROR] /clone/src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java:[42,5] "
            "(sizes) MethodLength: Method length is 200 lines (max allowed is 150).\n"
            "[WARN] /clone/src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java:[88,1] "
            "(sizes) LineLength: Line is 130 chars (max 120).\n"
            "[INFO] BUILD FAILURE\n"
        )
        with TemporaryDirectory() as td:
            ok, violations = mvn_checkstyle_dry_run(
                td,
                runner=lambda _argv, _cwd: (1, sample_stdout, ""),
            )
            self.assertFalse(ok)
            self.assertEqual(len(violations), 2)
            self.assertEqual(violations[0]["severity"], "error")
            self.assertEqual(violations[0]["line"], 42)
            self.assertEqual(violations[0]["column"], 5)
            self.assertEqual(violations[0]["rule"], "MethodLength")
            self.assertIn("Method length is 200 lines", violations[0]["message"])
            self.assertEqual(violations[1]["severity"], "warn")
            self.assertEqual(violations[1]["rule"], "LineLength")

    def test_non_java_file_lines_ignored(self):
        """Build banner lines like '[ERROR] /path/to/something:42:5: ...'
        that don't reference a .java file are NOT parsed as violations."""
        from scripts.lib.port_engine import mvn_checkstyle_dry_run
        sample_stdout = (
            "[ERROR] /clone/extra/pom.xml:1:1: Some build error\n"
            "[ERROR] /clone/Foo.java:10:1: Real violation [SomeRule]\n"
        )
        with TemporaryDirectory() as td:
            ok, violations = mvn_checkstyle_dry_run(
                td,
                runner=lambda _argv, _cwd: (1, sample_stdout, ""),
            )
            self.assertFalse(ok)
            self.assertEqual(len(violations), 1)
            self.assertIn("Foo.java", violations[0]["file"])

    def test_pom_file_argument_passed_to_mvn(self):
        from scripts.lib.port_engine import mvn_checkstyle_dry_run
        with TemporaryDirectory() as td:
            captured: List[List[str]] = []
            mvn_checkstyle_dry_run(
                td,
                pom_file="custom/pom.xml",
                runner=lambda argv, _cwd: (captured.append(argv), (0, "", ""))[1],
            )
            self.assertIn("--file", captured[0])
            idx = captured[0].index("--file")
            self.assertEqual(captured[0][idx + 1], "custom/pom.xml")


class TestDefaultAllowList(unittest.TestCase):
    def test_known_rebrand_present(self):
        self.assertEqual(DEFAULT_NAME_ALLOW_LIST.get("cadent_aperture_mx"), "emxdigital")


# ---------------------------------------------------------------------------
# Helper 11: imp_ext_shape_transform_java_to_go (Rule 36 inverse fixture side)
# ---------------------------------------------------------------------------


class TestImpExtShapeTransformJavaToGo(unittest.TestCase):
    """D3.8 canary F4: when port-java2go re-authors a Java IT auction-request
    into a Go flat exemplary fixture, ``imp.ext.{bidder_name}`` (Java per-bidder
    slot) must be renamed to ``imp.ext.bidder`` (Go canonical) so the emitted
    ``mockBidRequest`` parses against Go's standard-two-phase unmarshal."""

    def test_single_imp_kobler_shape_transforms(self):
        """Concrete D3.8 kobler-canary case: imp.ext.kobler.test=false →
        imp.ext.bidder.test=false."""
        fixture = {
            "id": "request_id",
            "imp": [
                {
                    "id": "imp_id",
                    "banner": {"h": 250, "w": 300},
                    "ext": {"kobler": {"test": False}},
                }
            ],
            "tmax": 5000,
        }
        out = imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertEqual(out["imp"][0]["ext"], {"bidder": {"test": False}})
        # Sibling fields untouched.
        self.assertEqual(out["imp"][0]["banner"], {"h": 250, "w": 300})
        self.assertEqual(out["tmax"], 5000)

    def test_multi_imp_each_gets_transform(self):
        fixture = {
            "imp": [
                {"id": "i1", "ext": {"adverxo": {"placementId": 1}}},
                {"id": "i2", "ext": {"adverxo": {"placementId": 2}, "tid": "abc"}},
                {"id": "i3", "ext": {"adverxo": {"placementId": 3}}},
            ],
        }
        out = imp_ext_shape_transform_java_to_go(fixture, "adverxo")
        for imp in out["imp"]:
            self.assertIn("bidder", imp["ext"])
            self.assertNotIn("adverxo", imp["ext"])
        # Other keys preserved.
        self.assertEqual(out["imp"][1]["ext"]["tid"], "abc")
        # Values forwarded intact.
        self.assertEqual(out["imp"][0]["ext"]["bidder"], {"placementId": 1})
        self.assertEqual(out["imp"][2]["ext"]["bidder"], {"placementId": 3})

    def test_prebid_key_passes_through_untouched(self):
        """imp.ext.prebid (rare but possible alongside the bidder slot) MUST
        pass through unchanged; only the per-bidder-name slot key changes."""
        fixture = {
            "imp": [
                {
                    "id": "imp_id",
                    "ext": {
                        "kobler": {"test": False},
                        "prebid": {"storedrequest": {"id": "stored-1"}},
                    },
                }
            ],
        }
        out = imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertEqual(
            out["imp"][0]["ext"]["prebid"],
            {"storedrequest": {"id": "stored-1"}},
        )
        self.assertEqual(out["imp"][0]["ext"]["bidder"], {"test": False})
        self.assertNotIn("kobler", out["imp"][0]["ext"])

    def test_imp_ext_missing_bidder_slot_left_untouched(self):
        """Already-Go-shaped or malformed Java fixture: imp.ext has no key
        named after the Java bidder. Helper leaves the imp untouched (no
        error) so the emitter can recover gracefully."""
        fixture = {
            "imp": [
                {"id": "i1", "ext": {"tid": "t1", "gpid": "/gp/1"}},
            ],
        }
        out = imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertEqual(out["imp"][0]["ext"], {"tid": "t1", "gpid": "/gp/1"})
        # No 'bidder' key was created.
        self.assertNotIn("bidder", out["imp"][0]["ext"])

    def test_imp_ext_already_has_bidder_key_raises(self):
        """Defensive: if imp.ext already carries a 'bidder' key alongside the
        Java slot, the helper aborts rather than silently overwriting."""
        fixture = {
            "imp": [
                {
                    "id": "i1",
                    "ext": {
                        "kobler": {"test": False},
                        "bidder": {"existing": True},
                    },
                }
            ],
        }
        with self.assertRaises(ValueError) as ctx:
            imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertIn("bidder", str(ctx.exception))
        self.assertIn("kobler", str(ctx.exception))

    def test_empty_imp_array_no_op(self):
        fixture = {"id": "request_id", "imp": []}
        out = imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertEqual(out, {"id": "request_id", "imp": []})

    def test_missing_imp_key_no_op(self):
        """Rare malformed fixture lacking imp[] entirely — helper returns
        the input shape (deep-copied) without erroring."""
        fixture = {"id": "request_id", "tmax": 5000}
        out = imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertEqual(out, {"id": "request_id", "tmax": 5000})

    def test_input_dict_not_mutated(self):
        """Clone semantics: helper returns a new dict; the caller's input is
        unchanged so a downstream pass can compare before/after if needed."""
        fixture = {
            "imp": [{"id": "i1", "ext": {"kobler": {"test": False}}}],
        }
        original_snapshot = json.loads(json.dumps(fixture))
        _ = imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertEqual(fixture, original_snapshot)
        # Specifically: the Java slot key still present in the input.
        self.assertIn("kobler", fixture["imp"][0]["ext"])
        self.assertNotIn("bidder", fixture["imp"][0]["ext"])

    def test_empty_bidder_name_raises(self):
        with self.assertRaises(ValueError):
            imp_ext_shape_transform_java_to_go({"imp": []}, "")

    def test_non_dict_imp_entries_skipped_safely(self):
        """Defensive: malformed imp[] entries that are not dicts (e.g. a stray
        string) are skipped; valid entries still transform."""
        fixture = {
            "imp": [
                "not-a-dict",
                {"id": "i2", "ext": {"kobler": {"test": True}}},
                None,
            ],
        }
        out = imp_ext_shape_transform_java_to_go(fixture, "kobler")
        self.assertEqual(out["imp"][0], "not-a-dict")
        self.assertEqual(out["imp"][1]["ext"], {"bidder": {"test": True}})
        self.assertIsNone(out["imp"][2])


# ---------------------------------------------------------------------------
# Helper 12: simulate_makerequests_mutations (D3.8 F-new-16 fixture-body sim)
# ---------------------------------------------------------------------------


class TestSimulateMakerequestsMutations(unittest.TestCase):
    """D3.8 F-new-16: simulate the Go adapter's MakeRequests mutations on a
    mockBidRequest to produce the expected ``httpCalls[].expectedRequest.body``
    for flat exemplary fixtures. Covers 15 canonical mutation ops drawn from
    kobler / vungle / adkernelAdn / thetradedesk / adverxo upstream adapters."""

    def _kobler_shape_request(self) -> Dict[str, Any]:
        """Minimal kobler-shape request with Device + User + single banner imp."""
        return {
            "id": "request_id",
            "device": {"ip": "1.2.3.4", "ipv6": "::1", "ua": "Mozilla/5.0"},
            "user": {"buyeruid": "abc"},
            "imp": [
                {
                    "id": "imp_id",
                    "banner": {"h": 250, "w": 300},
                    "ext": {"bidder": {"test": False}},
                }
            ],
            "tmax": 5000,
        }

    def test_empty_mutations_returns_deepcopy(self):
        req = self._kobler_shape_request()
        out = simulate_makerequests_mutations(req, [])
        self.assertEqual(out, req)
        # Verify deepcopy: mutating the result must not affect the input.
        out["imp"][0]["banner"]["w"] = 999
        self.assertEqual(req["imp"][0]["banner"]["w"], 300)

    def test_input_dict_not_mutated(self):
        req = self._kobler_shape_request()
        snapshot = json.loads(json.dumps(req))
        _ = simulate_makerequests_mutations(req, [
            {"kind": "device-zero-fields", "fields": ["ip", "ipv6"]},
            {"kind": "user-null"},
        ])
        # Caller's dict unchanged.
        self.assertEqual(req, snapshot)

    def test_unknown_op_kind_raises(self):
        with self.assertRaises(ValueError) as ctx:
            simulate_makerequests_mutations({}, [{"kind": "no-such-op"}])
        self.assertIn("no-such-op", str(ctx.exception))

    # --- Op 1: device-zero-fields ------------------------------------------

    def test_device_zero_fields_zeros_named_fields(self):
        req = self._kobler_shape_request()
        out = simulate_makerequests_mutations(req, [
            {"kind": "device-zero-fields", "fields": ["ip", "ipv6"]},
        ])
        self.assertEqual(out["device"]["ip"], "")
        self.assertEqual(out["device"]["ipv6"], "")
        # Other fields preserved.
        self.assertEqual(out["device"]["ua"], "Mozilla/5.0")

    def test_device_zero_fields_only_present_fields_zeroed(self):
        """Defensive: device with only IPv6 present (no IP) → only IPv6 zeroed."""
        req = {
            "id": "r1",
            "device": {"ipv6": "::1", "ua": "Mozilla/5.0"},
            "imp": [],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "device-zero-fields", "fields": ["ip", "ipv6"]},
        ])
        self.assertEqual(out["device"]["ipv6"], "")
        self.assertNotIn("ip", out["device"])
        self.assertEqual(out["device"]["ua"], "Mozilla/5.0")

    def test_device_zero_fields_no_device_key_no_op(self):
        req = {"id": "r1", "imp": []}
        out = simulate_makerequests_mutations(req, [
            {"kind": "device-zero-fields", "fields": ["ip", "ipv6"]},
        ])
        self.assertNotIn("device", out)

    # --- Op 2: user-null ----------------------------------------------------

    def test_user_null_removes_user_key(self):
        req = self._kobler_shape_request()
        out = simulate_makerequests_mutations(req, [{"kind": "user-null"}])
        self.assertNotIn("user", out)
        # Other fields untouched.
        self.assertEqual(out["device"], req["device"])

    def test_user_null_no_user_key_no_op(self):
        req = {"id": "r1", "imp": []}
        out = simulate_makerequests_mutations(req, [{"kind": "user-null"}])
        self.assertEqual(out, {"id": "r1", "imp": []})

    # --- Op 3: imp-bidfloor-convert-to-usd ---------------------------------

    def test_imp_bidfloor_convert_usd_passthrough_when_already_usd(self):
        req = {
            "id": "r1",
            "imp": [
                {"id": "i1", "bidfloor": 1.5, "bidfloorcur": "USD"},
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-bidfloor-convert-to-usd"},
        ])
        self.assertEqual(out["imp"][0]["bidfloor"], 1.5)
        self.assertEqual(out["imp"][0]["bidfloorcur"], "USD")

    def test_imp_bidfloor_convert_usd_retags_non_usd(self):
        """bidfloorcur != USD with positive bidfloor → bidfloorcur set to USD,
        bidfloor untouched (caller pre-converts)."""
        req = {
            "id": "r1",
            "imp": [
                {"id": "i1", "bidfloor": 1.42, "bidfloorcur": "EUR"},
                {"id": "i2", "bidfloor": 0, "bidfloorcur": "EUR"},  # 0 → no-op
                {"id": "i3"},  # no bidfloor → no-op
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-bidfloor-convert-to-usd"},
        ])
        # i1: re-tagged.
        self.assertEqual(out["imp"][0]["bidfloorcur"], "USD")
        self.assertEqual(out["imp"][0]["bidfloor"], 1.42)
        # i2: 0 bidfloor → unchanged.
        self.assertEqual(out["imp"][1]["bidfloorcur"], "EUR")
        # i3: missing fields → unchanged.
        self.assertNotIn("bidfloorcur", out["imp"][2])

    # --- Op 4: imp-ext-strip-after-extraction ------------------------------

    def test_imp_ext_strip_removes_ext_per_imp(self):
        req = {
            "imp": [
                {"id": "i1", "ext": {"bidder": {"x": 1}}},
                {"id": "i2", "ext": {"bidder": {"x": 2}, "tid": "abc"}},
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-ext-strip-after-extraction"},
        ])
        for imp in out["imp"]:
            self.assertNotIn("ext", imp)

    # --- Op 5: imp-ext-rewrap-with-bidder-slot -----------------------------

    def test_imp_ext_rewrap_adds_named_slot_with_bidder_content(self):
        """vungle pattern: imp.ext gains a `vungle` key carrying bidder content;
        bidder slot remains (mirrors the embedded-struct marshaler shape)."""
        req = {
            "imp": [
                {
                    "id": "i1",
                    "ext": {
                        "bidder": {"placementRefId": "abc", "pubAppStoreID": "xyz"},
                        "prebid": {"storedrequest": {"id": "stored"}},
                    },
                }
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-ext-rewrap-with-bidder-slot", "slot_name": "vungle"},
        ])
        ext = out["imp"][0]["ext"]
        self.assertIn("vungle", ext)
        self.assertEqual(ext["vungle"], {"placementRefId": "abc", "pubAppStoreID": "xyz"})
        # bidder slot preserved (vungleImpressionExt embeds ExtImpBidder).
        self.assertIn("bidder", ext)
        # prebid passes through.
        self.assertEqual(ext["prebid"], {"storedrequest": {"id": "stored"}})

    def test_imp_ext_rewrap_missing_slot_name_raises(self):
        with self.assertRaises(ValueError):
            simulate_makerequests_mutations(
                {"imp": [{"ext": {"bidder": {}}}]},
                [{"kind": "imp-ext-rewrap-with-bidder-slot"}],
            )

    # --- Op 6: site-null ---------------------------------------------------

    def test_site_null_removes_site_key(self):
        req = {"site": {"id": "s1", "domain": "example.com"}, "imp": []}
        out = simulate_makerequests_mutations(req, [{"kind": "site-null"}])
        self.assertNotIn("site", out)

    # --- Op 7: app-replace-with-synthesis ----------------------------------

    def test_app_replace_with_synthesis_uses_payload(self):
        req = {"site": {"id": "s1"}, "imp": []}
        synth = {"publisher": {"id": "vungle-pub-123"}, "id": "appstore-id"}
        out = simulate_makerequests_mutations(req, [
            {"kind": "app-replace-with-synthesis", "app_synthesis_payload": synth},
        ])
        self.assertEqual(out["app"], synth)
        # Deep-copied: mutating output must not touch the op's payload.
        out["app"]["publisher"]["id"] = "mutated"
        self.assertEqual(synth["publisher"]["id"], "vungle-pub-123")

    def test_app_replace_with_synthesis_missing_payload_raises(self):
        with self.assertRaises(ValueError):
            simulate_makerequests_mutations(
                {"imp": []},
                [{"kind": "app-replace-with-synthesis"}],
            )

    # --- Op 8: site-publisher-rewrite --------------------------------------

    def test_site_publisher_rewrite_overwrites_id(self):
        req = {
            "site": {"id": "s1", "publisher": {"id": "old", "name": "OldCo"}},
            "imp": [],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "site-publisher-rewrite", "publisher_id": "ttd-supply-1"},
        ])
        self.assertEqual(out["site"]["publisher"]["id"], "ttd-supply-1")
        # Other publisher fields preserved.
        self.assertEqual(out["site"]["publisher"]["name"], "OldCo")

    def test_site_publisher_rewrite_no_site_no_op(self):
        req = {"imp": []}
        out = simulate_makerequests_mutations(req, [
            {"kind": "site-publisher-rewrite", "publisher_id": "p1"},
        ])
        self.assertNotIn("site", out)

    # --- Op 9: app-publisher-rewrite ---------------------------------------

    def test_app_publisher_rewrite_overwrites_id(self):
        req = {
            "app": {"id": "a1", "publisher": {"id": "old"}},
            "imp": [],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "app-publisher-rewrite", "publisher_id": "ttd-supply-2"},
        ])
        self.assertEqual(out["app"]["publisher"]["id"], "ttd-supply-2")

    # --- Op 10: site-publisher-null ----------------------------------------

    def test_site_publisher_null_removes_publisher(self):
        req = {
            "site": {"id": "s1", "publisher": {"id": "p1"}, "domain": "x.com"},
            "imp": [],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "site-publisher-null"},
        ])
        self.assertNotIn("publisher", out["site"])
        # Other site fields preserved.
        self.assertEqual(out["site"]["domain"], "x.com")

    # --- Op 11: site-domain-clear ------------------------------------------

    def test_site_domain_clear_sets_empty_string(self):
        """Go's `Site.Domain = ""` produces an empty-string field on the wire,
        not a missing key (Site.Domain has no omitempty tag)."""
        req = {"site": {"id": "s1", "domain": "example.com"}, "imp": []}
        out = simulate_makerequests_mutations(req, [
            {"kind": "site-domain-clear"},
        ])
        self.assertIn("domain", out["site"])
        self.assertEqual(out["site"]["domain"], "")

    # --- Op 12: app-publisher-null -----------------------------------------

    def test_app_publisher_null_removes_publisher(self):
        req = {"app": {"id": "a1", "publisher": {"id": "p1"}}, "imp": []}
        out = simulate_makerequests_mutations(req, [
            {"kind": "app-publisher-null"},
        ])
        self.assertNotIn("publisher", out["app"])

    # --- Op 13: banner-format-fill-wh --------------------------------------

    def test_banner_format_fill_wh_fills_when_missing(self):
        req = {
            "imp": [
                {
                    "id": "i1",
                    "banner": {"format": [{"w": 728, "h": 90}, {"w": 300, "h": 250}]},
                },
                # imp with W/H already set — must NOT be touched.
                {
                    "id": "i2",
                    "banner": {"w": 320, "h": 50, "format": [{"w": 728, "h": 90}]},
                },
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "banner-format-fill-wh"},
        ])
        # i1: w/h filled from format[0]; format[0] dropped.
        self.assertEqual(out["imp"][0]["banner"]["w"], 728)
        self.assertEqual(out["imp"][0]["banner"]["h"], 90)
        self.assertEqual(out["imp"][0]["banner"]["format"], [{"w": 300, "h": 250}])
        # i2: untouched (had explicit w/h).
        self.assertEqual(out["imp"][1]["banner"]["w"], 320)
        self.assertEqual(out["imp"][1]["banner"]["h"], 50)
        self.assertEqual(out["imp"][1]["banner"]["format"], [{"w": 728, "h": 90}])

    def test_banner_format_fill_wh_no_banner_no_op(self):
        req = {"imp": [{"id": "i1", "video": {"w": 640, "h": 480}}]}
        out = simulate_makerequests_mutations(req, [
            {"kind": "banner-format-fill-wh"},
        ])
        self.assertNotIn("banner", out["imp"][0])

    # --- Op 14: imp-tagid-from-ext -----------------------------------------

    def test_imp_tagid_from_ext_copies_value(self):
        """Vungle's `imp.TagID = bidderImpExt.PlacementRefID` mirrored as
        a per-imp tagid copy from a named field inside imp.ext.{any-slot}."""
        req = {
            "imp": [
                {
                    "id": "i1",
                    "ext": {
                        "bidder": {"placementRefId": "vungle-placement-abc"},
                        "vungle": {"placementRefId": "vungle-placement-abc"},
                    },
                }
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-tagid-from-ext", "ext_field_name": "placementRefId"},
        ])
        self.assertEqual(out["imp"][0]["tagid"], "vungle-placement-abc")

    def test_imp_tagid_from_ext_skipped_when_field_absent(self):
        req = {"imp": [{"id": "i1", "ext": {"bidder": {"x": 1}}}]}
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-tagid-from-ext", "ext_field_name": "placementRefId"},
        ])
        self.assertNotIn("tagid", out["imp"][0])

    # --- Op 15: currency-normalize-to-list ---------------------------------

    def test_currency_normalize_to_list_appends_when_missing(self):
        req = {"cur": ["EUR"], "imp": []}
        out = simulate_makerequests_mutations(req, [
            {"kind": "currency-normalize-to-list", "currency": "USD"},
        ])
        self.assertEqual(out["cur"], ["EUR", "USD"])

    def test_currency_normalize_to_list_no_op_when_present(self):
        req = {"cur": ["USD", "EUR"], "imp": []}
        out = simulate_makerequests_mutations(req, [
            {"kind": "currency-normalize-to-list", "currency": "USD"},
        ])
        self.assertEqual(out["cur"], ["USD", "EUR"])

    def test_currency_normalize_to_list_creates_list_when_missing(self):
        req = {"imp": []}
        out = simulate_makerequests_mutations(req, [
            {"kind": "currency-normalize-to-list", "currency": "USD"},
        ])
        self.assertEqual(out["cur"], ["USD"])

    # --- Multi-op sequence + ordering -------------------------------------

    def test_kobler_full_sequence_applies_in_order(self):
        """Three-op kobler simulation: zero device IP/IPv6, null user, append USD
        currency. Verifies ops accumulate; output reflects all three changes."""
        req = self._kobler_shape_request()
        out = simulate_makerequests_mutations(req, [
            {"kind": "device-zero-fields", "fields": ["ip", "ipv6"]},
            {"kind": "user-null"},
            {"kind": "currency-normalize-to-list", "currency": "USD"},
        ])
        self.assertEqual(out["device"]["ip"], "")
        self.assertEqual(out["device"]["ipv6"], "")
        self.assertNotIn("user", out)
        self.assertEqual(out["cur"], ["USD"])

    def test_adkernel_multi_imp_sequence(self):
        """adkernelAdn-shape: two imps, one banner+W/H, one banner+format-only.
        Sequence: strip imp.ext, null Site.Publisher, clear Site.Domain,
        null App.Publisher, fill Banner.W/H from format[0]."""
        req = {
            "site": {"id": "s1", "publisher": {"id": "p1"}, "domain": "example.com"},
            "app": {"id": "a1", "publisher": {"id": "ap1"}},
            "imp": [
                {"id": "i1", "ext": {"bidder": {}}, "banner": {"w": 320, "h": 50}},
                {"id": "i2", "ext": {"bidder": {}}, "banner": {"format": [{"w": 728, "h": 90}]}},
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-ext-strip-after-extraction"},
            {"kind": "site-publisher-null"},
            {"kind": "site-domain-clear"},
            {"kind": "app-publisher-null"},
            {"kind": "banner-format-fill-wh"},
        ])
        # imp.ext stripped on every imp.
        self.assertNotIn("ext", out["imp"][0])
        self.assertNotIn("ext", out["imp"][1])
        # Site.Publisher nulled, domain cleared.
        self.assertNotIn("publisher", out["site"])
        self.assertEqual(out["site"]["domain"], "")
        # App.Publisher nulled.
        self.assertNotIn("publisher", out["app"])
        # Banner W/H untouched on i1 (already set), filled on i2.
        self.assertEqual(out["imp"][0]["banner"]["w"], 320)
        self.assertEqual(out["imp"][1]["banner"]["w"], 728)
        self.assertEqual(out["imp"][1]["banner"]["h"], 90)
        self.assertEqual(out["imp"][1]["banner"]["format"], [])

    def test_vungle_site_to_app_synthesis_sequence(self):
        """vungle-shape: imp.ext rewrap, imp.tagid from ext, site=null,
        app=synthesis-payload."""
        req = {
            "site": {"id": "site-1"},
            "imp": [
                {
                    "id": "i1",
                    "ext": {"bidder": {"placementRefId": "p-abc", "pubAppStoreID": "x123"}},
                    "banner": {"w": 320, "h": 50},
                }
            ],
        }
        out = simulate_makerequests_mutations(req, [
            {"kind": "imp-ext-rewrap-with-bidder-slot", "slot_name": "vungle"},
            {"kind": "imp-tagid-from-ext", "ext_field_name": "placementRefId"},
            {"kind": "site-null"},
            {
                "kind": "app-replace-with-synthesis",
                "app_synthesis_payload": {"id": "x123"},
            },
        ])
        self.assertNotIn("site", out)
        self.assertEqual(out["app"], {"id": "x123"})
        self.assertEqual(out["imp"][0]["tagid"], "p-abc")
        # vungle slot installed; bidder slot retained (matches embedded-struct shape).
        self.assertIn("vungle", out["imp"][0]["ext"])
        self.assertIn("bidder", out["imp"][0]["ext"])

    def test_unknown_op_kind_includes_supported_kinds(self):
        """Defensive: error message lists supported kinds for operator
        diagnostics (caller can grep the list)."""
        try:
            simulate_makerequests_mutations({}, [{"kind": "site-publisher-frobnicate"}])
        except ValueError as e:
            msg = str(e)
            self.assertIn("site-publisher-frobnicate", msg)
            # A few sentinel kinds the operator can use to confirm coverage.
            self.assertIn("user-null", msg)
            self.assertIn("device-zero-fields", msg)
            return
        self.fail("expected ValueError")


# ---------------------------------------------------------------------------
# Helper 13: exemplary_fixture_assemble_java_to_go (D3.8 canary v2: F-new-9/10/11/13)
# ---------------------------------------------------------------------------


# Repo-local path to the prebid-server-java clone (hosting the kobler IT
# fixtures used by the canary-shape regression test). Keep aligned with
# the rest of port_engine.py's path conventions.
_JAVA_CLONE = Path("/Users/quantum/Documents/GitHub/prebid-server-java")
_KOBLER_IT_DIR = (
    _JAVA_CLONE
    / "src/test/resources/org/prebid/server/it/openrtb2/kobler"
)


def _load_kobler_it_fixtures() -> Dict[str, Dict[str, Any]]:
    """Load the kobler 4-file IT fixture set as plain dicts.

    The canary-shape regression test (``test_kobler_shape_passthrough``)
    exercises the helper end-to-end against actual Java IT inputs, so the
    test reads the fixtures from the upstream-Java clone at runtime.
    """
    return {
        "auction_request": json.loads(
            (_KOBLER_IT_DIR / "test-auction-kobler-request.json").read_text()
        ),
        "auction_response": json.loads(
            (_KOBLER_IT_DIR / "test-auction-kobler-response.json").read_text()
        ),
        "bid_request": json.loads(
            (_KOBLER_IT_DIR / "test-kobler-bid-request.json").read_text()
        ),
        "bid_response": json.loads(
            (_KOBLER_IT_DIR / "test-kobler-bid-response.json").read_text()
        ),
    }


class TestExemplaryFixtureAssembleJavaToGo(unittest.TestCase):
    """D3.8 canary v2/v3 helper: bundles F-new-9/10/11/13 fixture-authoring
    concerns plus the F-new-22 opt-in empty-user injection into a single
    ctx-assembly call so future Java→Go canaries don't rediscover the
    same shape contract.

    Coverage map:
      F-new-9  : test_cur_fallback_when_bid_response_missing_cur,
                 test_cur_no_fallback_when_bid_response_has_cur,
                 test_cur_lenient_on_conflict
      F-new-10 : test_test_endpoint_default,
                 test_test_endpoint_override,
                 test_test_endpoint_constant_canonical
      F-new-11 : test_expected_bids_from_bare_bid_response,
                 test_expected_bids_empty_seatbid,
                 test_expected_bids_default_type_banner,
                 test_expected_bids_custom_default_type
      F-new-12 : test_imp_ids_from_mock_bid_request,
                 test_imp_ids_empty_when_no_imp
      F-new-13 : test_expected_request_body_simulator_called,
                 test_expected_request_body_default_passthrough
      F-new-22 : test_inject_empty_user_when_absent,
                 test_inject_empty_user_when_user_is_None,
                 test_inject_empty_user_no_op_when_user_present,
                 test_inject_empty_user_default_false_preserves_absent_user
      Misc     : test_kobler_shape_passthrough,
                 test_imp_ext_shape_transform_applied,
                 test_input_dicts_not_mutated,
                 test_empty_bidder_name_raises
    """

    # ----- F-new-9 cur fallback ------------------------------------------------

    def test_cur_fallback_when_bid_response_missing_cur(self):
        """F-new-9: bid-response without ``cur``; auction-response with
        ``cur: USD`` → http_calls[0].response.cur should be ``USD``."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r", "cur": "USD"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},  # no cur
            java_bidder_name="kobler",
        )
        self.assertEqual(ctx["http_calls"][0]["response"]["cur"], "USD")

    def test_cur_no_fallback_when_bid_response_has_cur(self):
        """F-new-9: bid-response cur=EUR, auction-response cur=USD →
        http_calls[0].response.cur should remain EUR (don't override the
        bid-response's own cur)."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r", "cur": "USD"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": [], "cur": "EUR"},
            java_bidder_name="kobler",
        )
        self.assertEqual(ctx["http_calls"][0]["response"]["cur"], "EUR")

    def test_cur_lenient_on_conflict(self):
        """F-new-9 design decision: lenient mode on cur conflict — the
        bid-response value wins, no error raised. Per the audit doc,
        bid-response is closer to upstream-true ground truth."""
        # Should NOT raise even though the two responses disagree.
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r", "cur": "USD"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": [], "cur": "EUR"},
            java_bidder_name="kobler",
        )
        # Lenient: bid-response wins.
        self.assertEqual(ctx["http_calls"][0]["response"]["cur"], "EUR")

    # ----- F-new-10 TEST_ENDPOINT ---------------------------------------------

    def test_test_endpoint_default(self):
        """F-new-10: default ``test_endpoint`` matches the canonical Builder
        URL bidder-test.go.j2 emits."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
        )
        self.assertEqual(
            ctx["http_calls"][0]["uri"],
            "https://test.example.com/bid",
        )

    def test_test_endpoint_override(self):
        """F-new-10: caller can override ``test_endpoint`` if a future
        bidder-test.go variant uses a non-standard URL."""
        custom = "https://custom.example.com/bid"
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
            test_endpoint=custom,
        )
        self.assertEqual(ctx["http_calls"][0]["uri"], custom)

    def test_test_endpoint_constant_canonical(self):
        """F-new-10: the ``TEST_ENDPOINT`` module constant matches the URL
        emitted by ``bidder-test.go.j2``'s Builder() invocation. This is
        the single-source-of-truth contract — if either side changes, the
        other must follow in the same commit."""
        self.assertEqual(TEST_ENDPOINT, "https://test.example.com/bid")

    # ----- F-new-11 expected_bids ---------------------------------------------

    def test_expected_bids_from_bare_bid_response(self):
        """F-new-11: bid-response has the BARE bid (no exp, no ext);
        auction-response has the framework-ENRICHED bid (with exp,
        ext.origbidcpm). Helper must derive expected_bids from the bare
        bid-response — using auction-response would inject the framework
        enrichments into the fixture and the Go test would fail JSON
        comparison."""
        bare_bid = {
            "id": "bid_id",
            "impid": "imp_id",
            "price": 3.33,
        }
        enriched_bid = {
            **bare_bid,
            "exp": 300,  # framework-added
            "ext": {  # framework-added
                "origbidcpm": 3.33,
                "prebid": {"meta": {"adaptercode": "kobler"}, "type": "banner"},
            },
        }
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={
                "id": "r",
                "cur": "USD",
                "seatbid": [{"bid": [enriched_bid]}],
            },
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": [{"bid": [bare_bid]}]},
            java_bidder_name="kobler",
        )
        self.assertEqual(len(ctx["expected_bids"]), 1)
        self.assertEqual(ctx["expected_bids"][0]["bid"], bare_bid)
        # The bid is BARE: no exp, no ext fields beyond what bid-response had.
        self.assertNotIn("exp", ctx["expected_bids"][0]["bid"])
        self.assertNotIn("ext", ctx["expected_bids"][0]["bid"])

    def test_expected_bids_empty_seatbid(self):
        """F-new-11: empty seatbid → expected_bids is an empty list (no
        crash, no None)."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
        )
        self.assertEqual(ctx["expected_bids"], [])

    def test_expected_bids_default_type_banner(self):
        """F-new-11: default ``default_bid_type`` is ``"banner"``."""
        bid = {"id": "b1", "impid": "i1", "price": 1.0}
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": [{"bid": [bid]}]},
            java_bidder_name="kobler",
        )
        self.assertEqual(ctx["expected_bids"][0]["type"], "banner")

    def test_expected_bids_custom_default_type(self):
        """F-new-11: vungle-shape — caller passes ``default_bid_type='video'``
        to match the hardcoded BidType.video the upstream adapter returns."""
        bid = {"id": "b1", "impid": "i1", "price": 1.0}
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r", "imp": []},
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": [{"bid": [bid]}]},
            java_bidder_name="vungle",
            default_bid_type="video",
        )
        self.assertEqual(ctx["expected_bids"][0]["type"], "video")

    # ----- F-new-12 imp_ids ----------------------------------------------------

    def test_imp_ids_from_mock_bid_request(self):
        """F-new-12: multi-imp auction-request → imp_ids contains all imp
        IDs in their original order."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={
                "id": "r",
                "imp": [
                    {"id": "i1", "ext": {"adverxo": {"placementId": 1}}},
                    {"id": "i2", "ext": {"adverxo": {"placementId": 2}}},
                    {"id": "i3", "ext": {"adverxo": {"placementId": 3}}},
                ],
            },
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="adverxo",
        )
        self.assertEqual(ctx["http_calls"][0]["imp_ids"], ["i1", "i2", "i3"])

    def test_imp_ids_empty_when_no_imp(self):
        """F-new-12: malformed auction-request without imp[] → imp_ids is
        an empty list (no crash, no error)."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={"id": "r"},  # no imp[]
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
        )
        self.assertEqual(ctx["http_calls"][0]["imp_ids"], [])

    # ----- F-new-13 expected_request_body --------------------------------------

    def test_expected_request_body_simulator_called(self):
        """F-new-13 non-passthrough: caller supplies a simulator that
        returns a modified mock_bid_request; assert http_calls[0].body
        carries the modification."""
        def simulator(req: Dict[str, Any]) -> Dict[str, Any]:
            out = dict(req)
            out["secure"] = 1  # simulate adapter adding secure=1
            return out

        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={
                "id": "r",
                "imp": [
                    {
                        "id": "i1",
                        "ext": {"kobler": {"test": False}},
                    }
                ],
            },
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
            expected_request_body_simulator=simulator,
        )
        self.assertEqual(ctx["http_calls"][0]["body"]["secure"], 1)
        # mock_bid_request itself remains unmutated by simulator-output.
        self.assertNotIn("secure", ctx["mock_bid_request"])

    def test_expected_request_body_default_passthrough(self):
        """F-new-13 passthrough fallback: no simulator → body equals
        mock_bid_request (the F4-transformed form, NOT the original Java
        auction-request)."""
        java_auction_request = {
            "id": "r",
            "imp": [
                {
                    "id": "i1",
                    "ext": {"kobler": {"test": False}},
                }
            ],
        }
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request=java_auction_request,
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
        )
        # Body equals mock_bid_request (with imp.ext.bidder, NOT imp.ext.kobler).
        self.assertEqual(ctx["http_calls"][0]["body"], ctx["mock_bid_request"])
        self.assertEqual(
            ctx["http_calls"][0]["body"]["imp"][0]["ext"],
            {"bidder": {"test": False}},
        )
        # Body is NOT the original Java auction-request shape.
        self.assertNotIn("kobler", ctx["http_calls"][0]["body"]["imp"][0]["ext"])

    # ----- F-new-22 inject_empty_user_if_missing -------------------------------

    def test_inject_empty_user_when_absent(self):
        """F-new-22: auction-request has no ``user`` key + flag=True →
        mock_bid_request gets ``user: {}`` injected, and the passthrough
        expectedRequest.body carries the same injected empty user
        (matches what the harness will feed to MakeRequests)."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={
                "id": "r",
                "imp": [
                    {"id": "i1", "ext": {"vungle": {"placementId": "p1"}}},
                ],
                # no "user" key
            },
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="vungle",
            inject_empty_user_if_missing=True,
        )
        self.assertEqual(ctx["mock_bid_request"]["user"], {})
        # Passthrough body sees the post-injection mock_bid_request.
        self.assertEqual(ctx["http_calls"][0]["body"]["user"], {})

    def test_inject_empty_user_when_user_is_None(self):
        """F-new-22: auction-request has ``user: null`` (explicit None) +
        flag=True → mock_bid_request's user becomes ``{}``. Treats
        explicit None the same as absent (both fail Go's
        ``request.User.X`` direct deref)."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={
                "id": "r",
                "imp": [
                    {"id": "i1", "ext": {"vungle": {"placementId": "p1"}}},
                ],
                "user": None,
            },
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="vungle",
            inject_empty_user_if_missing=True,
        )
        self.assertEqual(ctx["mock_bid_request"]["user"], {})

    def test_inject_empty_user_no_op_when_user_present(self):
        """F-new-22: auction-request already carries ``user`` with content
        + flag=True → injection is a no-op; the existing user object
        passes through untouched. Don't clobber real fixture data."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={
                "id": "r",
                "imp": [
                    {"id": "i1", "ext": {"vungle": {"placementId": "p1"}}},
                ],
                "user": {"buyeruid": "abc"},
            },
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="vungle",
            inject_empty_user_if_missing=True,
        )
        self.assertEqual(
            ctx["mock_bid_request"]["user"], {"buyeruid": "abc"}
        )

    def test_inject_empty_user_default_false_preserves_absent_user(self):
        """F-new-22 backward-compat: default flag (False) leaves an absent
        user absent. kobler/aax canary v2 callers rely on this; the
        helper must NOT silently change their emitted ctx."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={
                "id": "r",
                "imp": [
                    {"id": "i1", "ext": {"kobler": {"test": False}}},
                ],
                # no "user" key, default flag = False.
            },
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
        )
        self.assertNotIn("user", ctx["mock_bid_request"])

    # ----- Misc / integration --------------------------------------------------

    def test_kobler_shape_passthrough(self):
        """Canary-v2 regression: feeding kobler's actual 4-file fixtures
        through the helper (default simulator = passthrough) produces a
        ctx that matches what canary v2 emitted modulo dict-key ordering.

        The expected ctx is reconstructed from
        ``.tmp/full-loop/2026-05-05T0721Z-5c7f/go/adapters/kobler/koblertest/exemplary/canonical_banner.json``.
        Canary v2 was the source-of-truth shape that gate 2 passed
        against; if this test breaks, the helper drifted from the
        gate-passing shape contract.
        """
        if not _KOBLER_IT_DIR.is_dir():
            self.skipTest(f"kobler IT fixture dir absent: {_KOBLER_IT_DIR}")
        f = _load_kobler_it_fixtures()
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request=f["auction_request"],
            java_auction_response=f["auction_response"],
            java_bid_request=f["bid_request"],
            java_bid_response=f["bid_response"],
            java_bidder_name="kobler",
        )

        # mock_bid_request: F4-transformed kobler auction-request.
        self.assertEqual(
            ctx["mock_bid_request"]["imp"][0]["ext"],
            {"bidder": {"test": False}},
        )
        self.assertNotIn("kobler", ctx["mock_bid_request"]["imp"][0]["ext"])

        # http_calls[0] shape.
        self.assertEqual(len(ctx["http_calls"]), 1)
        call = ctx["http_calls"][0]
        self.assertEqual(call["uri"], "https://test.example.com/bid")
        self.assertEqual(call["status"], 200)
        self.assertEqual(call["imp_ids"], ["imp_id"])
        # body == mockBidRequest (passthrough fallback).
        self.assertEqual(call["body"], ctx["mock_bid_request"])
        # response: cur fallback applied (kobler bid-response has no cur).
        self.assertEqual(call["response"]["cur"], "USD")

        # expected_bids: bare bid from bid-response (no exp, no ext).
        self.assertEqual(len(ctx["expected_bids"]), 1)
        eb = ctx["expected_bids"][0]
        self.assertEqual(eb["type"], "banner")
        self.assertNotIn("exp", eb["bid"])
        self.assertNotIn("ext", eb["bid"])
        # Specific field values from kobler test-kobler-bid-response.json.
        self.assertEqual(eb["bid"]["id"], "bid_id")
        self.assertEqual(eb["bid"]["impid"], "imp_id")
        self.assertEqual(eb["bid"]["price"], 3.33)

        # expected_currency: from auction-response.cur (USD).
        self.assertEqual(ctx["expected_currency"], "USD")

    def test_imp_ext_shape_transform_applied(self):
        """The helper applies F4 (imp.ext.<bidder> → imp.ext.bidder) to
        the auction-request before assembling the ctx."""
        ctx = exemplary_fixture_assemble_java_to_go(
            java_auction_request={
                "id": "r",
                "imp": [
                    {
                        "id": "imp_id",
                        "banner": {"h": 250, "w": 300},
                        "ext": {"kobler": {"test": False}},
                    }
                ],
            },
            java_auction_response={"id": "r"},
            java_bid_request={"id": "r"},
            java_bid_response={"id": "r", "seatbid": []},
            java_bidder_name="kobler",
        )
        # The Java per-bidder slot is renamed to Go-canonical "bidder".
        self.assertEqual(
            ctx["mock_bid_request"]["imp"][0]["ext"],
            {"bidder": {"test": False}},
        )
        # The Java slot key is GONE from the emitted ctx.
        self.assertNotIn(
            "kobler",
            ctx["mock_bid_request"]["imp"][0]["ext"],
        )

    def test_input_dicts_not_mutated(self):
        """Pass-by-reference safety: the helper deepcopies internally so
        the caller's input dicts come out unchanged after the call.
        Lets the caller compare before/after or feed the same fixtures
        into multiple helpers without surprise mutation."""
        java_auction_request = {
            "id": "r",
            "imp": [
                {"id": "i1", "ext": {"kobler": {"test": False}}},
            ],
        }
        java_auction_response = {"id": "r", "cur": "USD"}
        java_bid_request = {"id": "r"}
        # Critical: bid-response WITHOUT cur — the helper would otherwise
        # be tempted to mutate the input to add cur.
        java_bid_response = {"id": "r", "seatbid": []}

        # Snapshot inputs for after-comparison.
        snapshot = {
            "auction_request": json.loads(json.dumps(java_auction_request)),
            "auction_response": json.loads(json.dumps(java_auction_response)),
            "bid_request": json.loads(json.dumps(java_bid_request)),
            "bid_response": json.loads(json.dumps(java_bid_response)),
        }

        _ = exemplary_fixture_assemble_java_to_go(
            java_auction_request=java_auction_request,
            java_auction_response=java_auction_response,
            java_bid_request=java_bid_request,
            java_bid_response=java_bid_response,
            java_bidder_name="kobler",
        )

        # All inputs preserved verbatim.
        self.assertEqual(java_auction_request, snapshot["auction_request"])
        self.assertEqual(java_auction_response, snapshot["auction_response"])
        self.assertEqual(java_bid_request, snapshot["bid_request"])
        self.assertEqual(java_bid_response, snapshot["bid_response"])
        # Specifically: F4 did not rename in-place.
        self.assertIn("kobler", java_auction_request["imp"][0]["ext"])
        self.assertNotIn("bidder", java_auction_request["imp"][0]["ext"])
        # Specifically: cur fallback did not add cur to the input.
        self.assertNotIn("cur", java_bid_response)

    def test_empty_bidder_name_raises(self):
        """Defensive: empty/None bidder_name raises ValueError (forwarded
        from the F4 helper but caught here too so the failure surfaces at
        the wrapper layer's signature)."""
        with self.assertRaises(ValueError):
            exemplary_fixture_assemble_java_to_go(
                java_auction_request={"id": "r", "imp": []},
                java_auction_response={"id": "r"},
                java_bid_request={"id": "r"},
                java_bid_response={"id": "r", "seatbid": []},
                java_bidder_name="",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
