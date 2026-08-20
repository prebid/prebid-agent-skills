"""The read-error / upstream-drift split must come from the pin, not from taste.

WHY
    A drift finding means only that the golden and current master disagree. Fixing
    it correctly depends on which of two things produced it, and the two have
    opposite remedies: a read error is fixed in the field with the pin unchanged,
    while upstream drift must NOT be fixed in the field -- editing it makes the
    spec assert a value at a commit nobody read.

    Getting it wrong preserves a wrong value behind an explanation, or edits a
    field out of agreement with its own pin. `classify-drift.py` decides by
    re-running the detector's own comparison at each golden's pin, and these tests
    pin that it routes on that result and nothing else.

Run: python3 -m unittest scripts.tests.test_classify_drift -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "classify-drift.py"

_spec = importlib.util.spec_from_file_location("cd_", SCRIPT)
if _spec is None or _spec.loader is None:
    raise unittest.SkipTest(f"cannot load {SCRIPT}")
cd_ = importlib.util.module_from_spec(_spec)
sys.modules["cd_"] = cd_
_spec.loader.exec_module(cd_)


class _StubFinding:
    def __init__(self, type_: str) -> None:
        self.type = type_


class TestClassify(unittest.TestCase):
    """`kobler` is used because a Go golden with that name exists in the corpus,
    so the path check passes; what the comparison returns is stubbed."""

    def _run(self, at_pin_types: list[str], finding_type: str, checkout: bool = True):
        report = {"scan_set": ["kobler/go"], "findings": [
            {"bidder": "kobler", "language": "go", "type": finding_type,
             "severity": "warn", "detail": {}}]}
        original = cd_.sfu.compare_bidder_go
        cd_.sfu.compare_bidder_go = lambda *a, **k: [_StubFinding(t) for t in at_pin_types]
        try:
            with tempfile.TemporaryDirectory() as td:
                rp = Path(td) / "r.json"
                rp.write_text(json.dumps(report))
                checkouts = {"go": Path(td)} if checkout else {}
                return cd_.classify(rp, checkouts)
        finally:
            cd_.sfu.compare_bidder_go = original

    def test_firing_at_the_pin_is_a_read_error(self):
        got = self._run(["endpoint_drift"], "endpoint_drift")
        self.assertEqual(1, len(got["read_error"]))
        self.assertEqual([], got["drift"])

    def test_firing_only_against_master_is_drift(self):
        got = self._run([], "endpoint_drift")
        self.assertEqual(1, len(got["drift"]))
        self.assertEqual([], got["read_error"])

    def test_a_different_type_at_the_pin_does_not_absolve_this_one(self):
        """Routing is per finding TYPE, not per bidder: one field being wrong at
        the pin says nothing about another field on the same golden."""
        got = self._run(["gvl_vendor_id_drift"], "endpoint_drift")
        self.assertEqual(1, len(got["drift"]))
        self.assertEqual([], got["read_error"])

    def test_no_checkout_is_unclassified_not_drift(self):
        """Without history there is no pin to compare at. Defaulting to either
        bucket would be a verdict the run did not earn."""
        got = self._run([], "endpoint_drift", checkout=False)
        self.assertEqual(1, len(got["unclassified"]))
        self.assertEqual([], got["drift"])
        self.assertEqual([], got["read_error"])

    def test_golden_without_a_pin_is_unclassified(self):
        with tempfile.TemporaryDirectory() as td:
            fixtures = Path(td) / "prebid-server-go" / "read" / "test-fixtures"
            fixtures.mkdir(parents=True)
            (fixtures / "nopin.golden.spec.yaml").write_text(
                yaml.safe_dump({"provenance": {"source": {}}}))
            report = Path(td) / "r.json"
            report.write_text(json.dumps({"scan_set": ["nopin/go"], "findings": [
                {"bidder": "nopin", "language": "go", "type": "endpoint_drift",
                 "severity": "warn", "detail": {}}]}))
            original_root = cd_.REPO_ROOT
            cd_.REPO_ROOT = Path(td)
            try:
                got = cd_.classify(report, {"go": Path(td)})
            finally:
                cd_.REPO_ROOT = original_root
            self.assertEqual(1, len(got["unclassified"]))


class TestCli(unittest.TestCase):
    def test_no_checkout_is_a_setup_error(self):
        with tempfile.TemporaryDirectory() as td:
            rp = Path(td) / "r.json"
            rp.write_text(json.dumps({"scan_set": [], "findings": []}))
            self.assertEqual(2, cd_.main(["--report", str(rp)]))

    def test_missing_report_is_a_setup_error(self):
        self.assertEqual(2, cd_.main(["--report", "/nonexistent/report.json",
                                      "--go-checkout", str(REPO_ROOT)]))


if __name__ == "__main__":
    unittest.main()
