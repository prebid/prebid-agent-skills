"""The accepted-drift gate must fail in both directions, and its keys must pin
the specific divergence rather than the shape of one.

WHY
    `sync-from-upstream.py` compares pinned goldens against current upstream
    master, so its resting state is not empty and the scheduled workflow was
    permanently red with a permanently open tracking issue -- the state that
    teaches people to stop reading a control.

    `.github/accepted-drift.txt` records which findings are known, so the job can
    be green when nothing NEW has moved. That only works if two properties hold,
    and both are checked here:

      1. A finding absent from the baseline fails. Otherwise the file is
         decoration.
      2. A baseline entry that fires nothing fails. Otherwise the file
         accumulates permissions for drift that was resolved, and eventually
         accepts more than anyone reviewed.

THE KEY-SHAPE PROPERTY
    `.github/accepted-warnings.txt`'s gate normalizes content hashes to `<hash>`
    so a fixture refresh does not invalidate every key. This one must NOT: the
    observed upstream value is what identifies the accepted divergence, and a
    second change to the same file is a new divergence nobody has reviewed. A key
    that collapsed the sha would silently inherit the first acceptance.

    `test_a_second_change_to_the_same_file_is_undeclared` is that property stated
    as a test, because it is the difference between a baseline and a blanket
    waiver.

Run: python3 -m unittest scripts.tests.test_drift_baseline -v
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check-drift-baseline.py"
BASELINE = REPO_ROOT / ".github" / "accepted-drift.txt"

_spec = importlib.util.spec_from_file_location("cdb", SCRIPT)
if _spec is None or _spec.loader is None:
    raise unittest.SkipTest(f"cannot load {SCRIPT}")
cdb = importlib.util.module_from_spec(_spec)
sys.modules["cdb"] = cdb
_spec.loader.exec_module(cdb)


def finding(**kw) -> dict:
    base = {"bidder": "kobler", "language": "java", "type": "fixture_content_drift",
            "severity": "warn",
            "detail": {"path": "src/test/x.json", "upstream_sha": "a" * 64}}
    base.update(kw)
    return base


def report(findings: list[dict]) -> dict:
    return {"scan_set": ["kobler/java"], "findings": findings}


def run(findings: list[dict], baseline_lines: list[str]) -> tuple[int, str]:
    """Run the gate against a synthetic report and baseline."""
    with tempfile.TemporaryDirectory() as td:
        rp = Path(td) / "report.json"
        rp.write_text(json.dumps(report(findings)))
        bp = Path(td) / "accepted-drift.txt"
        bp.write_text("# synthetic\n\n" + "\n".join(baseline_lines) + "\n")
        original = cdb.BASELINE_PATH
        cdb.BASELINE_PATH = bp
        try:
            proc_out: list[str] = []
            import contextlib, io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                try:
                    rc = cdb.main(["--report", str(rp)])
                except SystemExit as exc:   # load_report raises for setup errors
                    rc = int(exc.code or 0)
            proc_out.append(buf.getvalue())
            return rc, "".join(proc_out)
        finally:
            cdb.BASELINE_PATH = original


class TestKeyShape(unittest.TestCase):
    def test_key_carries_the_observed_upstream_value(self):
        k = cdb.make_key(finding())
        self.assertIn("a" * 64, k, "the sha must appear verbatim; collapsing it would let a "
                                   "second change inherit the first acceptance")
        self.assertIn("src/test/x.json", k)
        self.assertIn("kobler/java", k)

    def test_a_type_with_no_observer_is_not_silently_accepted(self):
        self.assertIsNone(cdb.make_key(finding(type="some_new_finding_type")))
        rc, out = run([finding(type="some_new_finding_type")], ["anything"])
        self.assertEqual(1, rc)
        self.assertIn("UNOBSERVABLE", out)

    def test_every_type_the_detector_can_emit_has_an_observer(self):
        """A finding type the detector emits but this script cannot observe is
        unacceptable-by-construction, which blocks the whole baseline. Keep the
        two in step."""
        source = (REPO_ROOT / "scripts" / "sync-from-upstream.py").read_text(encoding="utf-8")
        import re
        emitted = set(re.findall(r'"(\w+_drift|\w+_upstream|\w+_missing|new_yaml_field)"', source))
        # Presence findings are derived (`f"{w.kind}_file_missing"`) and are not
        # baselined: a file that vanished is not accepted drift, it is a refresh.
        emitted = {t for t in emitted if not t.endswith("_missing")}
        missing = sorted(emitted - set(cdb.OBSERVERS))
        self.assertEqual([], missing,
                         f"the detector emits these types with no observation defined, so they "
                         f"cannot be accepted: {missing}")


class TestBothDirections(unittest.TestCase):
    def test_undeclared_finding_fails(self):
        rc, out = run([finding()], ["sync-upstream | something | else/java | x"])
        self.assertEqual(1, rc)
        self.assertIn("UNDECLARED", out)

    def test_stale_entry_fails(self):
        rc, out = run([], [cdb.make_key(finding()), "sync-upstream | endpoint_drift | gone/go | y"])
        self.assertEqual(1, rc)
        self.assertIn("STALE ENTRY", out)

    def test_exact_match_passes(self):
        rc, out = run([finding()], [cdb.make_key(finding())])
        self.assertEqual(0, rc, out)

    def test_a_second_change_to_the_same_file_is_undeclared(self):
        """The property that makes this a baseline and not a waiver. The file is
        already accepted at one sha; changing again must not inherit that."""
        accepted = cdb.make_key(finding())
        moved = finding(detail={"path": "src/test/x.json", "upstream_sha": "b" * 64})
        rc, out = run([moved], [accepted])
        self.assertEqual(1, rc)
        self.assertIn("UNDECLARED", out)

    def test_empty_baseline_is_a_setup_error_not_a_pass(self):
        rc, out = run([finding()], [])
        self.assertEqual(2, rc)

    def test_zero_scan_set_is_a_setup_error_not_a_pass(self):
        with tempfile.TemporaryDirectory() as td:
            rp = Path(td) / "r.json"
            rp.write_text(json.dumps({"scan_set": [], "findings": []}))
            import contextlib, io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                try:
                    rc = cdb.main(["--report", str(rp)])
                except SystemExit as exc:
                    rc = int(exc.code or 0)
            self.assertEqual(2, rc, buf.getvalue())


class TestShippedBaseline(unittest.TestCase):
    def test_baseline_exists_and_every_line_parses(self):
        self.assertTrue(BASELINE.is_file(), f"missing {BASELINE.relative_to(REPO_ROOT)}")
        entries = cdb.read_baseline()
        self.assertGreater(len(entries), 0, "the shipped baseline is empty")
        for e in entries:
            parts = e.split(" | ")
            self.assertEqual(4, len(parts), f"malformed entry: {e!r}")
            self.assertEqual(cdb.SOURCE, parts[0])
            self.assertIn(parts[1], cdb.OBSERVERS,
                          f"entry names a type with no observer: {parts[1]!r}")

    def test_entries_are_unique(self):
        entries = cdb.read_baseline()
        dupes = sorted({e for e in entries if entries.count(e) > 1})
        self.assertEqual([], dupes, f"duplicate entries would mask a stale one: {dupes}")

    def test_every_entry_carries_a_cause(self):
        """An accepted divergence with no recorded cause is an unexplained
        exemption. Each entry must have a comment block somewhere above it."""
        text = BASELINE.read_text(encoding="utf-8")
        # Drop the header through the `# Entries: N` line, whose own trailing
        # count would otherwise read as an entry.
        body = text.split("# Entries:", 1)[-1].split("\n", 1)[-1]
        uncommented, seen_comment = [], False
        for line in body.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                seen_comment = True
            else:
                if not seen_comment:
                    uncommented.append(s)
        self.assertEqual([], uncommented,
                         "entries with no cause recorded above them:\n  " + "\n  ".join(uncommented))


if __name__ == "__main__":
    unittest.main()
