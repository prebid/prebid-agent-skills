#!/usr/bin/env python3
"""Self-tests for scripts/score_review_evals.py.

A scorer nobody has tested is worth nothing: it can report 100% recall against
a corpus it never read and nothing goes red. These tests drive both arms of
every gate -- the pass arm and the fail arm -- on synthetic fixtures, then
assert the real corpus is internally consistent.

Run: python3 -m unittest scripts.tests.test_score_review_evals -v
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import textwrap
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import score_review_evals as scorer  # noqa: E402

# A patch that carries every shape the matcher has to survive: diff markers, a
# YAML list item whose content starts with `-`, and a duplicated symbol.
SAMPLE_PATCH = textwrap.dedent("""\
    @@ -0,0 +1,12 @@
    +func getBidType(bid *openrtb2.Bid, imps []openrtb2.Imp) openrtb_ext.BidType {
    +\tfor i := range imps {
    +\t\tif imps[i].ID == bid.ImpID {
    +\t\t\tswitch {
    +\t\t\tcase imps[i].Banner != nil:
    +\t\t\t\treturn openrtb_ext.BidTypeBanner
    +\t\t\t}
    +\t\t}
    +\t}
    +\treturn openrtb_ext.BidTypeBanner
    +}
    \\ No newline at end of file
    """)

YAML_PATCH = textwrap.dedent("""\
    @@ -0,0 +1,4 @@
    +capabilities:
    +  site:
    +    mediaTypes:
    +      - banner
    """)


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class HarnessTestCase(unittest.TestCase):
    """Builds a throwaway corpus so the tests never depend on the real one."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="review-evals-selftest-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fixtures = self.tmp / "fixtures"
        self.actual = self.tmp / "actual"
        self.actual.mkdir(parents=True)
        self.baseline = self.tmp / "baseline.yaml"
        self.baseline.write_text(textwrap.dedent("""\
            # regression floor, not a certification
            version: 1
            global:
              min_recall: 1.0
              min_severity_agreement: 1.0
              max_forbidden_hits: 0
              max_unexpected: 0
            fixtures: {}
            """))

    # -- corpus construction ------------------------------------------------

    def make_fixture(self, fid="demo", outcome="defective", expected=None, forbidden=None,
                     files=None):
        d = self.fixtures / fid
        files = files if files is not None else [{
            "filename": "adapters/demo/demo.go", "status": "added",
            "additions": 12, "deletions": 0, "changes": 12,
            "previous_filename": None, "patch": SAMPLE_PATCH,
        }]
        write(d / "files.json", json.dumps(files, indent=2))
        write(d / "meta.yaml", textwrap.dedent(f"""\
            fixture_id: {fid}
            repo: prebid/prebid-server
            pr_number: 1
            language: go
            review_sha: 0000000000000000000000000000000000000000
            outcome: {outcome}
            file_count: {len(files)}
            """))
        body = {"pr": "prebid/prebid-server#1",
                "expected": expected if expected is not None else [DEFAULT_EXPECTED],
                "forbidden": forbidden or []}
        write(d / "expected.yaml", _yaml(body))
        return fid

    def write_actual(self, fid, findings, files_scanned=1, raw=None):
        p = self.actual / f"{fid}.yaml"
        if raw is not None:
            p.write_text(raw)
            return p
        p.write_text(_yaml({"fixture": fid, "files_scanned": files_scanned,
                            "findings": findings}))
        return p

    def run_scorer(self, *extra):
        """Swallow the scorer's human table so a failing assertion is readable.
        The verdict is taken from the exit code and the machine summary, never
        from the printed banner."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            return scorer.main([
                "--actual", str(self.actual),
                "--fixtures-dir", str(self.fixtures),
                "--baseline", str(self.baseline),
                *extra,
            ])


DEFAULT_EXPECTED = {
    "id": "demo-silent-banner-default",
    "path": "adapters/demo/demo.go",
    "anchor": "return openrtb_ext.BidTypeBanner",
    "symbol": "getBidType",
    "family": "bid-type-resolution",
    "severity": "FAIL",
    "source": "https://example.invalid/pull/1#discussion_r1",
    "why_it_matters": "silent default mis-types bids",
}

MATCHING_FINDING = {
    "path": "adapters/demo/demo.go",
    "anchor": "return openrtb_ext.BidTypeBanner",
    "symbol": "getBidType",
    "family": "bid-type-resolution",
    "severity": "FAIL",
}


def _yaml(obj) -> str:
    import yaml
    return yaml.safe_dump(obj, sort_keys=False, default_flow_style=False)


# ==========================================================================
# 1. a perfect run scores 1.0
# ==========================================================================

class TestPerfectRun(HarnessTestCase):

    def test_perfect_run_scores_one_and_exits_zero(self):
        fid = self.make_fixture()
        self.write_actual(fid, [MATCHING_FINDING])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        self.assertEqual(data["corpus"]["recall"], 1.0)
        self.assertEqual(data["corpus"]["forbidden_hits"], 0)
        self.assertEqual(data["corpus"]["unexpected"], 0)
        self.assertEqual(data["fixtures"][0]["severity_agreement"], 1.0)
        self.assertEqual(rc, scorer.EXIT_PASS)

    def test_machine_summary_and_human_table_agree(self):
        fid = self.make_fixture()
        self.write_actual(fid, [MATCHING_FINDING])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        table = scorer.render_table(data["fixtures"], {"global": {}}, [])
        self.assertIn("100.0%", table)
        self.assertIn(fid, table)


# ==========================================================================
# 2. a missed finding drops recall AND goes red
# ==========================================================================

class TestMissedFinding(HarnessTestCase):

    def test_missing_one_expected_finding_drops_recall_and_exits_nonzero(self):
        second = dict(DEFAULT_EXPECTED, id="demo-nested-imp-scan",
                      anchor="for i := range imps {", family="perf", severity="INFO")
        fid = self.make_fixture(expected=[DEFAULT_EXPECTED, second])
        self.write_actual(fid, [MATCHING_FINDING])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        self.assertEqual(data["corpus"]["recall"], 0.5)
        self.assertIn("demo-nested-imp-scan", data["fixtures"][0]["expected_missed"])
        self.assertEqual(rc, scorer.EXIT_FAIL)
        self.assertTrue(any("recall" in b for b in data["breaches"]))

    def test_finding_nothing_at_all_is_zero_recall_not_a_pass(self):
        fid = self.make_fixture()
        self.write_actual(fid, [])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 0.0)
        self.assertEqual(rc, scorer.EXIT_FAIL)

    def test_per_family_breakdown_names_the_missed_family(self):
        second = dict(DEFAULT_EXPECTED, id="demo-perf", anchor="for i := range imps {",
                      family="perf", severity="INFO")
        fid = self.make_fixture(expected=[DEFAULT_EXPECTED, second])
        self.write_actual(fid, [MATCHING_FINDING])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        fams = json.loads(summary.read_text())["fixtures"][0]["families"]
        self.assertEqual(fams["bid-type-resolution"]["matched"], 1)
        self.assertEqual(fams["perf"]["matched"], 0)
        self.assertEqual(fams["perf"]["missed"], ["demo-perf"])


# ==========================================================================
# 3. an invented finding raises false positives
# ==========================================================================

class TestFalsePositives(HarnessTestCase):

    def test_invented_finding_counts_as_unexpected_and_breaches_the_ceiling(self):
        fid = self.make_fixture()
        invented = {"path": "adapters/demo/demo.go", "anchor": "for i := range imps {",
                    "family": "perf", "severity": "FAIL"}
        self.write_actual(fid, [MATCHING_FINDING, invented])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        self.assertEqual(data["corpus"]["recall"], 1.0, "recall must not be diluted by an FP")
        self.assertEqual(data["corpus"]["unexpected"], 1)
        self.assertEqual(rc, scorer.EXIT_FAIL)
        self.assertTrue(any("unexpected" in b for b in data["breaches"]))

    def test_forbidden_finding_is_a_hard_hit_even_with_full_recall(self):
        forbidden = [{
            "id": "demo-http-endpoint-permitted",
            "path": "adapters/demo/demo.go",
            "anchor": "for i := range imps {",
            "family": "endpoint-config",
            "severity": "WARN",
            "source": "https://example.invalid/pull/1#discussion_r2",
            "why_it_matters": "maintainers ruled this permitted",
        }]
        fid = self.make_fixture(forbidden=forbidden)
        hit = {"path": "adapters/demo/demo.go", "anchor": "for i := range imps {",
               "family": "endpoint-config", "severity": "FAIL"}
        self.write_actual(fid, [MATCHING_FINDING, hit])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        self.assertEqual(data["corpus"]["recall"], 1.0)
        self.assertEqual(data["corpus"]["forbidden_hits"], 1)
        self.assertEqual(data["corpus"]["unexpected"], 0,
                         "a forbidden hit is classified, not double-counted as unexpected")
        self.assertEqual(rc, scorer.EXIT_FAIL)

    def test_clean_fixture_with_no_findings_passes(self):
        """The pass arm of the false-positive gate: saying nothing about a PR
        the maintainers merged unchanged is the correct answer."""
        forbidden = [{
            "id": "demo-permitted", "path": "adapters/demo/demo.go",
            "anchor": "for i := range imps {", "family": "perf", "severity": "WARN",
            "source": "https://example.invalid/pull/1#discussion_r2",
            "why_it_matters": "permitted",
        }]
        fid = self.make_fixture(outcome="clean", expected=[], forbidden=forbidden)
        self.write_actual(fid, [])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        self.assertIsNone(data["fixtures"][0]["recall"], "no expected findings -> recall is n/a")
        self.assertEqual(rc, scorer.EXIT_PASS)


# ==========================================================================
# 4. anchor matching is line-number independent
# ==========================================================================

class TestAnchorMatching(HarnessTestCase):

    def test_line_numbers_are_never_consulted(self):
        """Same finding, wildly different line/position metadata: still matches."""
        fid = self.make_fixture()
        for line in (1, 42, 100000, None):
            with self.subTest(line=line):
                self.write_actual(fid, [dict(MATCHING_FINDING, line=line, position=line)])
                summary = self.tmp / "summary.json"
                self.run_scorer("--json", str(summary))
                self.assertEqual(
                    json.loads(summary.read_text())["corpus"]["recall"], 1.0)

    def test_whitespace_and_indentation_differences_still_match(self):
        fid = self.make_fixture()
        self.write_actual(fid, [dict(
            MATCHING_FINDING,
            anchor="\t\treturn   openrtb_ext.BidTypeBanner\n")])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 1.0)

    def test_symbol_alone_matches_when_the_quoted_line_differs(self):
        fid = self.make_fixture()
        self.write_actual(fid, [{
            "path": "adapters/demo/demo.go",
            "anchor": "case imps[i].Banner != nil:",  # a different line in the same function
            "symbol": "getBidType",
            "family": "bid-type-resolution", "severity": "FAIL"}])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 1.0)

    def test_a_finding_in_another_file_never_matches(self):
        fid = self.make_fixture()
        self.write_actual(fid, [dict(MATCHING_FINDING, path="adapters/other/other.go")])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 0.0)
        self.assertEqual(rc, scorer.EXIT_FAIL)

    def test_two_expected_on_one_anchor_need_two_actual_findings(self):
        """One-to-one assignment: a single finding must not satisfy two entries."""
        twin = dict(DEFAULT_EXPECTED, id="demo-second-on-same-line",
                    family="mediatype-config-drift", severity="WARN")
        fid = self.make_fixture(expected=[DEFAULT_EXPECTED, twin])
        self.write_actual(fid, [MATCHING_FINDING])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 0.5)

        self.write_actual(fid, [MATCHING_FINDING,
                                dict(MATCHING_FINDING, family="mediatype-config-drift",
                                     severity="WARN")])
        self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 1.0)

    def test_file_level_anchor_requires_family_agreement(self):
        entry = dict(DEFAULT_EXPECTED, id="demo-noncanonical-file",
                     anchor=scorer.FILE_ANCHOR, family="canonical-artifacts",
                     severity="WARN")
        entry.pop("symbol")
        fid = self.make_fixture(expected=[entry])

        self.write_actual(fid, [{"path": "adapters/demo/demo.go", "family": "perf",
                                 "severity": "INFO"}])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 0.0,
                         "wrong family must not satisfy a file-level entry")

        self.write_actual(fid, [{"path": "adapters/demo/demo.go",
                                 "family": "canonical-artifacts", "severity": "WARN"}])
        self.run_scorer("--json", str(summary))
        self.assertEqual(json.loads(summary.read_text())["corpus"]["recall"], 1.0)

    def test_short_anchors_require_exact_equality(self):
        self.assertFalse(scorer.anchors_overlap("x", "return x from a long line"))
        self.assertTrue(scorer.anchors_overlap("x", "x"))
        self.assertTrue(scorer.anchors_overlap("return openrtb_ext.BidTypeBanner",
                                               "\treturn openrtb_ext.BidTypeBanner\n}"))

    def test_diff_markers_are_stripped_from_patches_but_not_from_anchors(self):
        """A YAML list item starts with '-'. Stripping markers from a hand-written
        anchor would silently turn `- banner` into `banner` and stop matching."""
        rendered = scorer.normalize_patch(YAML_PATCH)
        self.assertIn("mediaTypes: - banner", rendered)
        self.assertNotIn("@@", rendered)
        self.assertEqual(scorer.normalize_anchor("- banner"), "- banner")
        self.assertIn(scorer.normalize_anchor("- banner"), rendered)

    def test_normalize_path_tolerates_diff_prefixes(self):
        for variant in ("adapters/demo/demo.go", "./adapters/demo/demo.go",
                        "b/adapters/demo/demo.go"):
            self.assertEqual(scorer.normalize_path(variant), "adapters/demo/demo.go")


# ==========================================================================
# 5. an empty actual-findings file is an ERROR, not a clean pass
# ==========================================================================

class TestEmptyScanSetIsAnError(HarnessTestCase):

    def assert_error(self, raw, needle):
        fid = self.make_fixture()
        self.write_actual(fid, None, raw=raw)
        rc = self.run_scorer()
        self.assertEqual(rc, scorer.EXIT_ERROR)
        with self.assertRaises(scorer.HarnessError) as ctx:
            scorer.load_actual(self.actual / f"{fid}.yaml", fid)
        self.assertIn(needle, str(ctx.exception))

    def test_completely_empty_file_is_an_error(self):
        self.assert_error("", "empty scan set")

    def test_whitespace_only_file_is_an_error(self):
        self.assert_error("\n\n   \n", "empty scan set")

    def test_zero_files_scanned_is_an_error_even_with_findings_key(self):
        self.assert_error("fixture: demo\nfiles_scanned: 0\nfindings: []\n",
                          "Zero inputs is an error")

    def test_absent_files_scanned_is_an_error(self):
        self.assert_error("fixture: demo\nfindings: []\n", "scan set is part of its claim")

    def test_absent_findings_key_is_an_error_even_with_a_scan_set(self):
        self.assert_error("fixture: demo\nfiles_scanned: 1\n", "Absent is not")

    def test_missing_actual_file_is_an_error_not_a_clean_pass(self):
        self.make_fixture()
        rc = self.run_scorer()
        self.assertEqual(rc, scorer.EXIT_ERROR)

    def test_non_mapping_file_is_an_error(self):
        self.assert_error("- just\n- a\n- list\n", "must be a mapping")

    def test_declaring_more_files_than_the_fixture_holds_is_an_error(self):
        fid = self.make_fixture()
        self.write_actual(fid, [MATCHING_FINDING], files_scanned=99)
        self.assertEqual(self.run_scorer(), scorer.EXIT_ERROR)

    def test_explicit_empty_findings_with_a_real_scan_set_is_not_an_error(self):
        """The other arm: `findings: []` plus a non-zero scan set is a verdict,
        and it is allowed to be the right one."""
        fid = self.make_fixture(outcome="clean", expected=[])
        self.write_actual(fid, [], files_scanned=1)
        self.assertEqual(self.run_scorer(), scorer.EXIT_PASS)

    def test_a_partial_scan_set_is_reported_not_silently_accepted(self):
        files = [
            {"filename": "adapters/demo/demo.go", "status": "added", "additions": 12,
             "deletions": 0, "changes": 12, "previous_filename": None, "patch": SAMPLE_PATCH},
            {"filename": "static/bidder-info/demo.yaml", "status": "added", "additions": 4,
             "deletions": 0, "changes": 4, "previous_filename": None, "patch": YAML_PATCH},
        ]
        fid = self.make_fixture(files=files)
        self.write_actual(fid, [MATCHING_FINDING], files_scanned=1)
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        note = json.loads(summary.read_text())["fixtures"][0]["scan_note"]
        self.assertIsNotNone(note)
        self.assertIn("1/2", note)

    def test_an_empty_corpus_is_an_error(self):
        self.fixtures.mkdir(parents=True, exist_ok=True)
        self.assertEqual(self.run_scorer(), scorer.EXIT_ERROR)


# ==========================================================================
# severity calibration -- the failure this harness exists for
# ==========================================================================

class TestSeverityCalibration(HarnessTestCase):

    def test_under_rating_a_finding_is_detected_at_full_recall(self):
        """The Teal shape: the reviewer SAW the defect and rated it INFO because
        the source adapter did the same thing. Recall stays 1.0; only severity
        agreement moves, which is why recall alone cannot detect calibration."""
        fid = self.make_fixture()
        self.write_actual(fid, [dict(MATCHING_FINDING, severity="INFO")])
        summary = self.tmp / "summary.json"
        rc = self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        self.assertEqual(data["corpus"]["recall"], 1.0)
        self.assertEqual(data["corpus"]["severity_under_rated"], 1)
        self.assertEqual(data["fixtures"][0]["severity_agreement"], 0.0)
        self.assertEqual(rc, scorer.EXIT_FAIL)

    def test_over_rating_is_recorded_separately_from_under_rating(self):
        entry = dict(DEFAULT_EXPECTED, severity="INFO")
        fid = self.make_fixture(expected=[entry])
        self.write_actual(fid, [dict(MATCHING_FINDING, severity="FAIL")])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        data = json.loads(summary.read_text())
        self.assertEqual(data["corpus"]["severity_over_rated"], 1)
        self.assertEqual(data["corpus"]["severity_under_rated"], 0)

    def test_unrated_findings_do_not_count_toward_agreement(self):
        fid = self.make_fixture()
        finding = dict(MATCHING_FINDING)
        finding.pop("severity")
        self.write_actual(fid, [finding])
        summary = self.tmp / "summary.json"
        self.run_scorer("--json", str(summary))
        self.assertIsNone(json.loads(summary.read_text())["fixtures"][0]["severity_agreement"])


# ==========================================================================
# fixture integrity and baseline mechanics
# ==========================================================================

class TestFixtureIntegrity(HarnessTestCase):

    def test_an_anchor_absent_from_the_patch_makes_the_fixture_unscorable(self):
        bad = dict(DEFAULT_EXPECTED, anchor="this text is nowhere in the captured patch")
        fid = self.make_fixture(expected=[bad])
        self.write_actual(fid, [MATCHING_FINDING])
        self.assertEqual(self.run_scorer(), scorer.EXIT_ERROR)
        self.assertEqual(self.run_scorer("--validate-only"), scorer.EXIT_ERROR)

    def test_an_expected_path_absent_from_files_json_is_caught(self):
        bad = dict(DEFAULT_EXPECTED, path="adapters/ghost/ghost.go")
        self.make_fixture(expected=[bad])
        self.assertEqual(self.run_scorer("--validate-only"), scorer.EXIT_ERROR)

    def test_a_finding_without_a_source_is_caught(self):
        bad = dict(DEFAULT_EXPECTED)
        bad.pop("source")
        self.make_fixture(expected=[bad])
        self.assertEqual(self.run_scorer("--validate-only"), scorer.EXIT_ERROR)

    def test_duplicate_finding_ids_are_caught(self):
        twin = dict(DEFAULT_EXPECTED, anchor="for i := range imps {")
        self.make_fixture(expected=[DEFAULT_EXPECTED, twin])
        self.assertEqual(self.run_scorer("--validate-only"), scorer.EXIT_ERROR)

    def test_a_valid_fixture_passes_validate_only_without_any_actual_file(self):
        self.make_fixture()
        self.assertEqual(self.run_scorer("--validate-only"), scorer.EXIT_PASS)


class TestBaselineMechanics(HarnessTestCase):

    def test_a_zero_floor_lets_a_bad_run_pass_and_says_so(self):
        """The honest cost of an unmeasured floor, asserted rather than assumed."""
        self.baseline.write_text(textwrap.dedent("""\
            # regression floor, not a certification
            version: 1
            global:
              status: unmeasured
              min_recall: 0.0
              max_forbidden_hits: 0
              max_unexpected: 6
            fixtures: {}
            """))
        fid = self.make_fixture()
        self.write_actual(fid, [])
        self.assertEqual(self.run_scorer(), scorer.EXIT_PASS)
        table = scorer.render_table(
            [scorer.score_fixture(scorer.load_fixture(fid, self.fixtures),
                                  scorer.load_actual(self.actual / f"{fid}.yaml", fid))],
            scorer.load_baseline(self.baseline), [])
        self.assertIn("UNMEASURED", table)

    def test_recording_a_baseline_makes_the_next_regression_go_red(self):
        second = dict(DEFAULT_EXPECTED, id="demo-perf", anchor="for i := range imps {",
                      family="perf", severity="INFO")
        fid = self.make_fixture(expected=[DEFAULT_EXPECTED, second])
        both = [MATCHING_FINDING, {"path": "adapters/demo/demo.go",
                                   "anchor": "for i := range imps {",
                                   "family": "perf", "severity": "INFO"}]
        self.baseline.write_text(textwrap.dedent("""\
            # regression floor, not a certification
            version: 1
            global:
              status: unmeasured
              min_recall: 0.0
              max_forbidden_hits: 0
              max_unexpected: 6
            fixtures: {}
            """))
        self.write_actual(fid, both)
        self.assertEqual(self.run_scorer("--record-baseline", "--margin", "0.0"),
                         scorer.EXIT_PASS)

        import yaml
        recorded = yaml.safe_load(self.baseline.read_text())
        self.assertEqual(recorded["fixtures"][fid]["min_recall"], 1.0)
        self.assertNotIn("status", recorded["fixtures"][fid])
        self.assertIn("# regression floor, not a certification",
                      self.baseline.read_text())

        self.write_actual(fid, [MATCHING_FINDING])
        self.assertEqual(self.run_scorer(), scorer.EXIT_FAIL)

    def test_a_missing_baseline_is_an_error(self):
        self.make_fixture()
        self.baseline.unlink()
        self.assertEqual(self.run_scorer(), scorer.EXIT_ERROR)


# ==========================================================================
# the real corpus
# ==========================================================================

class TestRealCorpus(unittest.TestCase):
    """Integration: the shipped corpus must be internally consistent, and the
    committed floors must parse. This does not score any skill run."""

    def test_every_shipped_fixture_validates(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = scorer.main(["--validate-only"])
        self.assertEqual(rc, scorer.EXIT_PASS, buf.getvalue())
        self.assertIn("every anchor resolves", buf.getvalue())

    def test_corpus_has_the_two_mandatory_calibration_fixtures(self):
        ids = scorer.discover_fixtures(scorer.FIXTURES_DIR)
        self.assertIn("prebid-server-4765", ids)
        self.assertIn("prebid-server-java-4552", ids)

    def test_corpus_contains_at_least_two_clean_outcome_fixtures(self):
        clean = [f for f in scorer.discover_fixtures(scorer.FIXTURES_DIR)
                 if scorer.load_fixture(f, scorer.FIXTURES_DIR)["meta"]["outcome"] == "clean"]
        self.assertGreaterEqual(len(clean), 2, f"clean fixtures: {clean}")

    def test_every_forbidden_entry_lives_on_a_clean_or_defective_fixture_with_a_source(self):
        for fid in scorer.discover_fixtures(scorer.FIXTURES_DIR):
            fx = scorer.load_fixture(fid, scorer.FIXTURES_DIR)
            for entry in fx["forbidden"]:
                self.assertTrue(entry["source"].startswith("https://github.com/"),
                                f"{fid}/{entry['id']} has no traceable source")

    def test_every_expected_finding_traces_to_a_github_url(self):
        for fid in scorer.discover_fixtures(scorer.FIXTURES_DIR):
            fx = scorer.load_fixture(fid, scorer.FIXTURES_DIR)
            for entry in fx["expected"]:
                self.assertTrue(entry["source"].startswith("https://github.com/"),
                                f"{fid}/{entry['id']} source is not a GitHub URL")
                self.assertTrue(entry.get("why_it_matters"),
                                f"{fid}/{entry['id']} has no why_it_matters")

    def test_every_fixture_has_a_baseline_entry(self):
        baseline = scorer.load_baseline(scorer.BASELINE_PATH)
        for fid in scorer.discover_fixtures(scorer.FIXTURES_DIR):
            self.assertIn(fid, baseline.get("fixtures", {}),
                          f"{fid} has no committed floor; it would be scored against "
                          f"the global defaults silently")

    def test_forbidden_hits_are_never_tolerated_by_any_committed_floor(self):
        baseline = scorer.load_baseline(scorer.BASELINE_PATH)
        for fid in scorer.discover_fixtures(scorer.FIXTURES_DIR):
            floors = scorer.floors_for(baseline, fid)
            self.assertEqual(floors.get("max_forbidden_hits"), 0, fid)

    def test_fixtures_record_the_review_sha_not_only_the_merged_head(self):
        for fid in scorer.discover_fixtures(scorer.FIXTURES_DIR):
            meta = scorer.load_fixture(fid, scorer.FIXTURES_DIR)["meta"]
            self.assertEqual(len(meta["review_sha"]), 40, fid)
            self.assertTrue(meta.get("captured_at"), fid)
            self.assertIn(meta.get("outcome"), ("clean", "defective"), fid)



class TestRuleEpochs(unittest.TestCase):
    """A rule whose upstream fact postdates a PR could not have been raised on it.

    Verified in both directions: neutralised when the rule is newer than the
    fixture, counted normally when it is older. Without the second arm this is
    an amnesty, not a correction.
    """

    EPOCHS = [
        {"family": "upstream-api-drift", "scope": "java",
         "effective_from": "2026-07-09", "upstream": "java#4464"},
        {"family": "framework-idiom", "scope": "java",
         "effective_from": "2026-07-20", "upstream": "java#4444"},
    ]

    def test_rule_newer_than_fixture_is_neutralised(self):
        meta = {"epoch": "2026-03-23", "language": "java"}
        out = scorer.neutralised_families(meta, self.EPOCHS)
        self.assertEqual({"upstream-api-drift", "framework-idiom"}, set(out))

    def test_rule_older_than_fixture_still_applies(self):
        """The load-bearing arm: a PR reviewed after the change gets no excuse."""
        meta = {"epoch": "2026-08-18", "language": "java"}
        self.assertEqual({}, scorer.neutralised_families(meta, self.EPOCHS))

    def test_scope_confines_a_rule_to_its_language(self):
        meta = {"epoch": "2026-03-23", "language": "go"}
        self.assertEqual({}, scorer.neutralised_families(meta, self.EPOCHS))

    def test_missing_epoch_neutralises_nothing(self):
        """Absent metadata must not silently excuse findings."""
        self.assertEqual({}, scorer.neutralised_families({"language": "java"}, self.EPOCHS))

    def test_empty_registry_neutralises_nothing(self):
        meta = {"epoch": "2020-01-01", "language": "java"}
        self.assertEqual({}, scorer.neutralised_families(meta, []))

    def test_neutralised_findings_leave_the_unexpected_count(self):
        fx = {"id": "t", "meta": {}, "files": [{"filename": "a.java"}],
              "expected": [], "forbidden": [], "patches": {"a.java": ""},
              "neutralised_families": {"framework-idiom": {"upstream": "java#4444"}}}
        actual = {"findings": [
            {"path": "a.java", "anchor": "x", "severity": "FAIL", "family": "framework-idiom"},
            {"path": "a.java", "anchor": "y", "severity": "FAIL", "family": "error-handling"},
        ], "files_scanned": 1}
        res = scorer.score_fixture(fx, actual)
        self.assertEqual(1, res["unexpected"], "only the non-neutralised finding counts")
        self.assertEqual(1, res["neutralised"])
        self.assertEqual("java#4444", res["neutralised_detail"][0]["rule"],
                         "the exemption must name the rule that granted it")

    def test_registry_on_disk_parses_and_is_scoped(self):
        epochs = scorer.load_rule_epochs(REPO_ROOT / "review-evals")
        self.assertTrue(epochs, "rule-epochs.yaml should carry the known migrations")
        for rule in epochs:
            for field in ("family", "effective_from", "upstream", "what_changed"):
                self.assertIn(field, rule, f"{rule.get('family')} missing {field}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
