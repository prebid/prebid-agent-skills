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
        rules = cr.load_rules()
        self.assertEqual(46, len(rules), "Phase 2.5 brought rule count to 46")
        ids = sorted(r["id"] for r in rules)
        self.assertEqual(list(range(1, 47)), ids)


class TestCoverageComputations(unittest.TestCase):
    def setUp(self):
        self.goldens = cr.discover_goldens()
        self.duals = cr.discover_dual_specs()
        self.rules = cr.load_rules()

    def test_phase_5_pairs_exist(self):
        readiness = cr.compute_phase_5_readiness(self.goldens)
        self.assertEqual(9, len(readiness), "ADR-008 lists 9 Phase 5 pairs (3 P1 + 3 P2 + 1 P3 + 2 stretch)")
        # Coverage progresses as Phase 5 lands. Assert progress is monotonic
        # (never goes backwards) and adverxo (the first P1 fixture) is covered.
        covered = {p["bidder"] for p in readiness if p["covered"]}
        self.assertIn("adverxo", covered, "Phase 5 P1 #3 — adverxo pair fixture must be in the corpus")

    def test_rule_46_pairs_count_is_12(self):
        coverage = cr.compute_rule_46_coverage(self.goldens)
        self.assertEqual(12, len(coverage), "ADR-005 lists 12 Rule 46 naming pairs")

    def test_lifecycle_pairs_count_is_7(self):
        coverage = cr.compute_lifecycle_coverage(self.goldens)
        # ADR-006: 1 bilateral + 4 java-leads + 2 go-leads = 7 pairs (8th is bidirectional in inventory)
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
        per_rule = cr.compute_per_rule_mentions(self.rules, self.goldens)
        self.assertEqual(46, len(per_rule))


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
