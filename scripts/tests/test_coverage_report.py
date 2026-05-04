"""Phase 4.3 unit tests for scripts/coverage-report.py.

Verifies the report generates structurally, the --check drift gate works,
and the well-known coverage facts are reported correctly.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "coverage-report.py"

spec = importlib.util.spec_from_file_location("coverage_report", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise unittest.SkipTest(f"Cannot load {SCRIPT_PATH}")
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)


class TestDiscovery(unittest.TestCase):
    def test_discover_goldens_finds_corpus(self):
        g = cr.discover_goldens()
        self.assertGreater(len(g["go"]), 5, "Should find Go goldens")
        self.assertGreater(len(g["java"]), 5, "Should find Java goldens")
        self.assertIn("kobler", g["paired"], "kobler MUST be a paired golden")

    def test_discover_dual_specs_finds_files(self):
        d = cr.discover_dual_specs()
        self.assertIn("kobler", d, "kobler dual-spec must exist")
        self.assertNotIn("_parse_error", d.get("kobler", {}))

    def test_load_rules_returns_46(self):
        # Wave 11b B5 #6: hardcoded count + range(1, 47) literal removed; both
        # become tautologies once derived from len(rules). Test now validates
        # the non-trivial invariant: rule IDs are 1..N contiguous with no gaps.
        rules = cr.load_rules()
        self.assertGreater(len(rules), 0, "load_rules returned empty list")
        ids = sorted(r["id"] for r in rules)
        self.assertEqual(list(range(1, len(rules) + 1)), ids,
                         "Rule IDs must be 1..N contiguous (no gaps, no duplicates)")


class TestCoverageComputations(unittest.TestCase):
    def setUp(self):
        self.goldens = cr.discover_goldens()
        self.duals = cr.discover_dual_specs()
        self.rules = cr.load_rules()

    def test_phase_5_pairs_exist(self):
        readiness = cr.compute_phase_5_readiness(self.goldens)
        # ADR-008 listed 9 Phase 5 pairs (3 P1 + 3 P2 + 1 P3 + 2 stretch).
        # Phase D4.4 added beachfront as a 3rd stretch (ADR-007 F1 master)
        # so the count is now 10.
        self.assertEqual(10, len(readiness),
                         "ADR-008 + D4.4: 10 Phase 5 pairs (3 P1 + 3 P2 + 1 P3 + 3 stretch incl. beachfront)")
        # Coverage progresses as Phase 5 lands. Assert progress is monotonic
        # (never goes backwards) and adverxo (the first P1 fixture) is covered.
        covered = {p["bidder"] for p in readiness if p["covered"]}
        self.assertIn("adverxo", covered, "Phase 5 P1 #3 — adverxo pair fixture must be in the corpus")

    def test_rule_46_pairs_count_is_11(self):
        coverage = cr.compute_rule_46_coverage(self.goldens)
        self.assertEqual(11, len(coverage),
                         "ADR-005 lists 11 Rule 46 naming pairs (refined 2026-05-03 "
                         "from 12 — freewheel-ssp/freewheelssp removed; see ADR-005 "
                         "Excluded cases section)")

    def test_lifecycle_pairs_count_is_7(self):
        coverage = cr.compute_lifecycle_coverage(self.goldens)
        # ADR-006 (refined 2026-05-03): 2 bilateral + 1 java-leads + 0 go-leads
        # + 2 mirror-topology + 2 inverted-parent = 7 pairs (8th is bidirectional
        # in inventory)
        self.assertEqual(7, len(coverage), "ADR-006 lists 7 lifecycle-rename pairs (subset of 8 inventory entries)")

    def test_elementaltv_lifecycle_is_covered_bilateral(self):
        coverage = cr.compute_lifecycle_coverage(self.goldens)
        elementaltv = next(c for c in coverage if c["go"] == "elementaltv")
        self.assertEqual("bilateral", elementaltv["subtype"])
        self.assertTrue(elementaltv["has_go"])
        self.assertTrue(elementaltv["has_java"])

    def test_dual_spec_coherency_for_paired_goldens(self):
        coh = cr.compute_dual_spec_coherency(self.goldens, self.duals)
        # 7 dual-spec files; all 7 should have both go + java goldens (corpus invariant)
        for entry in coh:
            if "error" not in entry:
                self.assertTrue(entry["has_go"], f"{entry['bidder']}: dual-spec must have Go golden")
                self.assertTrue(entry["has_java"], f"{entry['bidder']}: dual-spec must have Java golden")

    def test_per_rule_mentions_returns_46_rows(self):
        # Wave 11b B5 #6: derived from len(self.rules) instead of hardcoded 46.
        per_rule = cr.compute_per_rule_mentions(self.rules, self.goldens)
        self.assertEqual(len(self.rules), len(per_rule),
                         "compute_per_rule_mentions must produce one row per loaded rule")


class TestRuleAppliedCounts(unittest.TestCase):
    """Phase D4.2: compute_rule_applied_counts() aggregates per-rule
    verdict counts across discovered port-report.json archives. Synthetic
    inputs prove the counting logic; production data flows in once
    operator-side port runs persist their reports."""

    def setUp(self):
        self.rules = cr.load_rules()

    def test_empty_reports_yields_zero_counts(self):
        rows = cr.compute_rule_applied_counts(self.rules, [])
        self.assertEqual(len(rows), len(self.rules))
        for row in rows:
            self.assertEqual(row["applied"], 0)
            self.assertEqual(row["applied_with_warning"], 0)
            self.assertEqual(row["skipped_not_applicable"], 0)
            self.assertEqual(row["skipped_source_side_only"], 0)
            self.assertEqual(row["exercised"], 0)
            self.assertEqual(row["total_runs_seen"], 0)

    def test_single_report_increments_counts(self):
        synthetic_report = {
            "port_report_version": "0.2.0",
            "rules_consumed": [
                {"rule_id": 1, "verdict": "applied", "summary": "x"},
                {"rule_id": 33, "verdict": "applied-with-warning", "summary": "y"},
                {"rule_id": 38, "verdict": "applied", "summary": "byte-copy"},
                {"rule_id": 42, "verdict": "skipped-not-applicable", "summary": ""},
                {"rule_id": 46, "verdict": "skipped-source-side-only", "summary": ""},
            ],
        }
        rows = cr.compute_rule_applied_counts(self.rules, [synthetic_report])
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id[1]["applied"], 1)
        self.assertEqual(by_id[1]["exercised"], 1)
        self.assertEqual(by_id[33]["applied_with_warning"], 1)
        self.assertEqual(by_id[33]["exercised"], 1)
        self.assertEqual(by_id[38]["applied"], 1)
        self.assertEqual(by_id[42]["skipped_not_applicable"], 1)
        self.assertEqual(by_id[42]["exercised"], 0)
        self.assertEqual(by_id[46]["skipped_source_side_only"], 1)
        for row in rows:
            self.assertEqual(row["total_runs_seen"], 1)

    def test_multiple_reports_aggregate(self):
        rep1 = {
            "port_report_version": "0.2.0",
            "rules_consumed": [{"rule_id": 38, "verdict": "applied"}],
        }
        rep2 = {
            "port_report_version": "0.2.0",
            "rules_consumed": [{"rule_id": 38, "verdict": "applied"}],
        }
        rep3 = {
            "port_report_version": "0.2.0",
            "rules_consumed": [{"rule_id": 38, "verdict": "applied-with-warning"}],
        }
        rows = cr.compute_rule_applied_counts(self.rules, [rep1, rep2, rep3])
        rule38 = next(r for r in rows if r["id"] == 38)
        self.assertEqual(rule38["applied"], 2)
        self.assertEqual(rule38["applied_with_warning"], 1)
        self.assertEqual(rule38["exercised"], 3)
        self.assertEqual(rule38["total_runs_seen"], 3)

    def test_unknown_rule_ids_silently_ignored(self):
        """A port report referencing a rule_id not in the rules YAML
        (e.g., from an older rules version) is ignored rather than crashing."""
        synthetic = {
            "port_report_version": "0.2.0",
            "rules_consumed": [
                {"rule_id": 9999, "verdict": "applied"},  # nonexistent rule
            ],
        }
        rows = cr.compute_rule_applied_counts(self.rules, [synthetic])
        # No crash, no row created for 9999.
        self.assertEqual(len(rows), len(self.rules))
        self.assertNotIn(9999, [r["id"] for r in rows])

    def test_malformed_verdict_silently_ignored(self):
        synthetic = {
            "port_report_version": "0.2.0",
            "rules_consumed": [
                {"rule_id": 38, "verdict": None},  # malformed; not a string
                {"rule_id": 38, "verdict": "bogus-verdict"},  # unknown enum
            ],
        }
        rows = cr.compute_rule_applied_counts(self.rules, [synthetic])
        rule38 = next(r for r in rows if r["id"] == 38)
        self.assertEqual(rule38["exercised"], 0)


class TestReportRender(unittest.TestCase):
    def test_render_produces_expected_sections(self):
        goldens = cr.discover_goldens()
        duals = cr.discover_dual_specs()
        rules = cr.load_rules()
        out = cr.render(goldens, duals, rules)
        for header in (
            "## 1. Golden inventory",
            "## 2. Phase 5 readiness",
            "## 3. Rule 46 naming-convention pairs",
            "## 4. Rule 43 lifecycle-rename pairs",
            "## 5. Java alias-empire parents",
            "## 6. Dual-spec assertion coherency",
            "## 7. Per-rule master-sample coverage",
            "## 7b. Port-translation rule applied-counts (per Phase D4.2)",
            "## 8. Top gaps to close",
        ):
            self.assertIn(header, out, f"Report missing required section: {header!r}")

    def test_on_disk_report_matches_render(self):
        """Drift gate: docs/coverage-report.md MUST be regenerable identical."""
        goldens = cr.discover_goldens()
        duals = cr.discover_dual_specs()
        rules = cr.load_rules()
        rendered = cr.render(goldens, duals, rules)
        if not cr.OUT_PATH.is_file():
            self.skipTest(f"No on-disk report at {cr.OUT_PATH}; run `make coverage` first")
        on_disk = cr.OUT_PATH.read_text()
        if rendered != on_disk:
            import difflib
            diff = "\n".join(list(difflib.unified_diff(
                on_disk.splitlines(),
                rendered.splitlines(),
                fromfile="docs/coverage-report.md",
                tofile="render(...) (rendered)",
                n=2,
            ))[:50])
            self.fail(
                "docs/coverage-report.md is out of sync with re-rendered output.\n"
                "Run `make coverage` to regenerate, then commit.\n\n"
                f"Diff (first 50 lines):\n{diff}"
            )


if __name__ == "__main__":
    unittest.main()
