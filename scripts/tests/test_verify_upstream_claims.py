"""Self-tests for the upstream-claims verifier.

A gate nobody has watched fail is not a gate -- this repo has shipped two of
those (a description lint whose threshold no file can reach, and a Rule-5 lint
whose pass arm has never executed). So every claim kind here is tested in BOTH
directions: it passes on the world as it is, and it fails on a synthetic world
representing the drift it exists to catch.

The synthetic worlds are the pre-drift upstream state from 2026-05-04, the one
that went undetected for sixteen weekly runs:
  - EndpointTemplateParams with 18 fields instead of 22
  - UsersyncerCreator.java still present
  - adapter-defaults.modifying-vast-xml-allowed: false
  - a jacoco `check` goal that does not exist in reality

Run: python3 -m unittest scripts.tests.test_verify_upstream_claims -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "verify_upstream_claims", REPO_ROOT / "scripts" / "verify-upstream-claims.py")
assert _spec and _spec.loader
vuc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vuc)

MANIFEST = REPO_ROOT / "scripts" / "upstream-claims.yaml"


def _run_quiet(argv: list[str]) -> int:
    """Invoke the CLI without leaking its report into the test output."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return vuc.main(argv)


def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")


class TestManifestIntegrity(unittest.TestCase):
    def test_manifest_parses_and_is_non_empty(self):
        import yaml
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        self.assertGreater(len(doc["claims"]), 0)
        self.assertIn("pins", doc)

    def test_every_claim_has_id_kind_repo_why_and_sites(self):
        """A claim with no site is unanchored: nothing in the repo depends on it,
        so it cannot be verified against what the skills actually say."""
        import yaml
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        for claim in doc["claims"]:
            for field in ("id", "kind", "repo", "why", "sites"):
                self.assertIn(field, claim, f"{claim.get('id', '?')} missing {field}")
            self.assertIn(claim["kind"], vuc.CHECKERS, f"{claim['id']} unknown kind")
            self.assertTrue(claim["sites"], f"{claim['id']} has no sites")

    def test_every_site_anchor_matches_exactly_once(self):
        """An anchor that matches many times is a word, not an anchor.

        An independent audit inverted two claims -- rewrote "multiformat is the
        DEFAULT" to "OPT-IN", and neutered every "checkstyle" mention -- and the
        gate stayed green, because both anchors were bare words that survived
        elsewhere in the file. 13 of 28 anchors had that property.
        """
        import yaml
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        weak = []
        for claim in doc["claims"]:
            for site in claim.get("sites") or []:
                path = REPO_ROOT / site["path"]
                if not path.is_file():
                    continue
                hits = path.read_text(encoding="utf-8").count(site["assert"])
                if hits != 1:
                    weak.append(f"{claim['id']} -> {site['path']}: {hits} matches for {site['assert']!r}")
        self.assertEqual([], weak,
                         "anchors must match exactly once; quote enough context to be unique:\n  "
                         + "\n  ".join(weak))

    def test_claim_ids_are_unique(self):
        import yaml
        doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        ids = [c["id"] for c in doc["claims"]]
        self.assertEqual(len(ids), len(set(ids)))


class TestSiteCheck(unittest.TestCase):
    def test_real_manifest_sites_are_anchored(self):
        self.assertEqual(_run_quiet(["--check-sites"]), 0)

    def test_missing_anchor_text_fails(self):
        """The hermetic half: a doc edited away from its registered claim."""
        with tempfile.TemporaryDirectory() as td:
            m = Path(td) / "m.yaml"
            m.write_text(
                # A valid SHAPE with a stale anchor: --check-sites never reads
                # upstream, but the manifest still has to be well-formed, so the
                # upstream keys are present and only the anchor is wrong.
                "version: 1\nclaims:\n"
                "  - id: t.anchor\n    kind: symbol\n    repo: go\n    why: t\n"
                "    symbol: adapters.Bidder\n    upstream_path: adapters\n"
                "    sites:\n      - path: README.md\n"
                "        assert: 'this string is not in the README'\n",
                encoding="utf-8")
            self.assertEqual(_run_quiet(["--manifest", str(m), "--check-sites"]), 1)

    def test_empty_manifest_is_a_setup_error_not_a_pass(self):
        """An empty scan set is a finding, not a clean verdict."""
        with tempfile.TemporaryDirectory() as td:
            m = Path(td) / "m.yaml"
            m.write_text("version: 1\nclaims: []\n", encoding="utf-8")
            self.assertEqual(_run_quiet(["--manifest", str(m), "--check-sites"]), 3)


class TestStructFields(unittest.TestCase):
    CLAIM = {
        "id": "t.struct", "kind": "struct_fields", "repo": "go",
        "upstream_path": "macros/macros.go", "struct": "EndpointTemplateParams",
        "expect": {"count": 22, "contains": ["Host", "NetworkId", "Bundle"]},
    }

    def _tree(self, root: Path, extra_fields: str) -> None:
        _write(root, "macros/macros.go", f"""
            package macros

            type EndpointTemplateParams struct {{
            \tHost        string
            \tPublisherID string
            {extra_fields}}}
            """)

    def test_detects_the_may_2026_macro_drift(self):
        """18 fields where the manifest says 22 -- the exact undetected drift."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._tree(root, "".join(f"\t{n} string\n" for n in
                                     ["ZoneID", "SourceId", "AccountID", "AdUnit", "MediaType",
                                      "GvlID", "PageID", "SupplyId", "ImpID", "SspId", "SspID",
                                      "SeatID", "TokenID", "PartnerId", "Region", "PlacementID"]))
            ok, detail = vuc.check_struct_fields(root, self.CLAIM)
            self.assertFalse(ok)
            self.assertIn("count 18 != 22", detail)
            self.assertIn("NetworkId", detail)

    def test_passes_when_field_set_matches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            names = ["ZoneID", "SourceId", "AccountID", "AdUnit", "MediaType", "GvlID",
                     "PageID", "SupplyId", "ImpID", "SspId", "SspID", "SeatID", "TokenID",
                     "PartnerId", "Region", "PlacementID", "NetworkId", "SiteDomain",
                     "AppDomain", "Bundle"]
            self._tree(root, "".join(f"\t{n} string\n" for n in names))
            ok, detail = vuc.check_struct_fields(root, self.CLAIM)
            self.assertTrue(ok, detail)

    def test_missing_struct_fails_rather_than_passing_vacuously(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "macros/macros.go", "package macros\n")
            ok, detail = vuc.check_struct_fields(root, self.CLAIM)
            self.assertFalse(ok)
            self.assertIn("not found", detail)


class TestAbsence(unittest.TestCase):
    CLAIM = {"id": "t.absent", "kind": "absence", "repo": "java",
             "upstream_path": "src/main/java", "absent": "UsersyncerCreator", "glob": "*.java"}

    def test_detects_a_deleted_api_that_is_still_present(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "src/main/java/UsersyncerCreator.java",
                   "public class UsersyncerCreator {}\n")
            ok, detail = vuc.check_absence(root, self.CLAIM)
            self.assertFalse(ok)
            self.assertIn("still present", detail)

    def test_passes_when_absent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "src/main/java/Other.java", "public class Other {}\n")
            ok, _ = vuc.check_absence(root, self.CLAIM)
            self.assertTrue(ok)

    def test_missing_scope_fails_rather_than_reporting_absence(self):
        """No files scanned must not read as 'absent'."""
        with tempfile.TemporaryDirectory() as td:
            ok, detail = vuc.check_absence(Path(td), self.CLAIM)
            self.assertFalse(ok)
            self.assertIn("scope not found", detail)


class TestEnforcement(unittest.TestCase):
    """The kind that exists because two 'upstream enforces X' claims were false."""

    NEGATIVE = {"id": "t.nogate", "kind": "enforcement", "repo": "java", "enforced": False,
                "artifacts": ["pom.xml"],
                "construct": r"jacoco-maven-plugin[\s\S]{0,1500}?<goal>check</goal>"}
    POSITIVE = {"id": "t.gate", "kind": "enforcement", "repo": "java", "enforced": True,
                "artifacts": ["extra/pom.xml"],
                "construct": r"maven-checkstyle-plugin[\s\S]{0,1200}?<phase>validate</phase>"}

    def test_phantom_gate_becoming_real_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "pom.xml", """
                <project><plugin><artifactId>jacoco-maven-plugin</artifactId>
                <executions><execution><goals><goal>check</goal></goals></execution></executions>
                </plugin></project>
                """)
            ok, detail = vuc.check_enforcement(root, self.NEGATIVE)
            self.assertFalse(ok)
            self.assertIn("claimed-absent enforcement IS present", detail)

    def test_report_only_jacoco_satisfies_the_no_gate_claim(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "pom.xml", """
                <project><plugin><artifactId>jacoco-maven-plugin</artifactId>
                <executions><execution><goals><goal>report</goal></goals></execution></executions>
                </plugin></project>
                """)
            ok, _ = vuc.check_enforcement(root, self.NEGATIVE)
            self.assertTrue(ok)

    def test_real_enforcement_disappearing_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "extra/pom.xml", "<project><plugin>"
                                          "<artifactId>maven-checkstyle-plugin</artifactId>"
                                          "</plugin></project>\n")
            ok, detail = vuc.check_enforcement(root, self.POSITIVE)
            self.assertFalse(ok)
            self.assertIn("not found", detail)


class TestConfigValue(unittest.TestCase):
    CLAIM = {"id": "t.cfg", "kind": "config_value", "repo": "java",
             "upstream_path": "application.yaml",
             "key": "adapter-defaults.modifying-vast-xml-allowed", "expect": True}

    def test_flipped_default_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "application.yaml", "adapter-defaults:\n  modifying-vast-xml-allowed: false\n")
            ok, detail = vuc.check_config_value(root, self.CLAIM)
            self.assertFalse(ok)
            self.assertIn("expected True", detail)

    def test_removed_key_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "application.yaml", "adapter-defaults:\n  ortb:\n    multiformat-supported: true\n")
            ok, detail = vuc.check_config_value(root, self.CLAIM)
            self.assertFalse(ok)
            self.assertIn("absent", detail)


class TestSymbol(unittest.TestCase):
    def test_generic_signature_is_recognised(self):
        """`func Clone[T any](` must not read as a missing symbol -- a naive
        `func Name\\(` regex reports a false absence on every Go generic."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "util/ptrutil/ptrutil.go",
                   "package ptrutil\n\nfunc Clone[T any](v *T) *T { return v }\n")
            ok, _ = vuc.check_symbol(root, {"upstream_path": "util/ptrutil", "symbol": "Clone"})
            self.assertTrue(ok)

    def test_absent_symbol_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "util/ptrutil/ptrutil.go", "package ptrutil\n")
            ok, detail = vuc.check_symbol(root, {"upstream_path": "util/ptrutil", "symbol": "Clone"})
            self.assertFalse(ok)
            self.assertIn("no definition", detail)


class TestManifestShape(unittest.TestCase):
    """A misspelled key used to widen a check's scope instead of failing it.

    `check_count` defaulted `upstream_path` to "." and `glob` to "*", so
    `upstrem_path:` scoped the search to the whole repository -- and the count
    still matched, so the claim reported PASS. That is worse than a crash: the
    gate is green for a check that never ran at the scope it names. Every
    scoping key is now mandatory and the manifest's shape is validated before
    any claim is checked.
    """

    GOOD = {
        "id": "t.count", "kind": "count", "repo": "java", "why": "t", "sites": [],
        "upstream_path": "src/main/resources/bidder-config", "glob": "appnexus.yaml",
        "mode": "matches", "pattern": r"(?m)^\s+\d+:\s", "expect": 95,
    }

    def _shape(self, claim: dict):
        return vuc.validate_manifest({"claims": [claim]})

    def test_clean_claim_produces_no_findings(self):
        self.assertEqual([], self._shape(dict(self.GOOD)))

    def test_real_manifest_shape_is_valid(self):
        import yaml
        findings = vuc.validate_manifest(yaml.safe_load(MANIFEST.read_text(encoding="utf-8")))
        self.assertEqual([], [f"{r.claim_id}: {r.detail}" for r in findings])

    def test_misspelled_scope_key_fails_instead_of_widening_the_search(self):
        claim = dict(self.GOOD)
        claim["upstrem_path"] = claim.pop("upstream_path")
        details = " | ".join(r.detail for r in self._shape(claim))
        self.assertIn("requires ['upstream_path']", details)
        self.assertIn("upstrem_path", details)

    def test_misspelled_glob_fails_instead_of_matching_every_file(self):
        claim = dict(self.GOOD)
        claim["glub"] = claim.pop("glob")
        self.assertIn("requires ['glob']", " ".join(r.detail for r in self._shape(claim)))

    def test_count_checker_no_longer_has_a_permissive_default(self):
        """Belt and braces: even called directly, a missing scope key must raise
        rather than silently search from the checkout root."""
        claim = dict(self.GOOD)
        claim.pop("upstream_path")
        with self.assertRaises(KeyError):
            vuc.check_count(REPO_ROOT, claim)

    def test_duplicate_id_is_a_finding(self):
        a = dict(self.GOOD)
        findings = vuc.validate_manifest({"claims": [a, dict(a)]})
        self.assertIn("duplicate claim id", " ".join(r.detail for r in findings))

    def test_bad_repo_is_a_finding(self):
        claim = dict(self.GOOD); claim["repo"] = "golang"
        self.assertIn("repo must be", " ".join(r.detail for r in self._shape(claim)))

    def test_invalid_shape_stops_the_run_rather_than_checking_at_a_wrong_scope(self):
        bad = dict(self.GOOD); bad["upstrem_path"] = bad.pop("upstream_path")
        with tempfile.TemporaryDirectory() as td:
            m = Path(td) / "m.yaml"
            import yaml
            m.write_text(yaml.safe_dump({"version": 1, "claims": [bad]}), encoding="utf-8")
            self.assertEqual(3, _run_quiet(["--manifest", str(m), "--check-sites"]))

    def test_malformed_claim_reports_the_key_rather_than_raising(self):
        """check_upstream's own guard, for a claim that reaches a checker anyway.

        The artifact must EXIST: check_enforcement skips unreadable artifacts, so
        with a bogus path the missing `construct` is never evaluated and the
        claim fails for an unrelated reason.
        """
        results = vuc.check_upstream(
            {"claims": [{"id": "t.z", "kind": "enforcement", "repo": "go", "why": "t",
                         "sites": [], "artifacts": ["README.md"], "enforced": True}]},
            {"go": REPO_ROOT})
        self.assertEqual(results[0].status, vuc.FAIL)
        self.assertIn("malformed claim", results[0].detail)
        self.assertIn("construct", results[0].detail)


class TestUnknownKind(unittest.TestCase):
    def test_unknown_kind_fails_loudly(self):
        results = vuc.check_upstream(
            {"claims": [{"id": "t.x", "kind": "not-a-kind", "repo": "go", "why": "t", "sites": []}]},
            {"go": REPO_ROOT})
        self.assertEqual(results[0].status, vuc.FAIL)
        self.assertIn("unknown kind", results[0].detail)

    def test_missing_checkout_warns_rather_than_silently_passing(self):
        results = vuc.check_upstream(
            {"claims": [{"id": "t.y", "kind": "symbol", "repo": "java", "why": "t", "sites": []}]},
            {"go": REPO_ROOT})
        self.assertEqual(results[0].status, vuc.WARN)


if __name__ == "__main__":
    unittest.main()
