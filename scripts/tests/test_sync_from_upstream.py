"""Phase 4.1 unit tests for scripts/sync-from-upstream.py.

Uses synthetic fetcher functions (no network) to exercise the comparison
logic against canned upstream-vs-golden divergences.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Callable, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "sync-from-upstream.py"

spec = importlib.util.spec_from_file_location("sync_from_upstream", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise unittest.SkipTest(f"Cannot load {SCRIPT_PATH}")
sfu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sfu)


def make_fetcher(files: dict) -> Callable[[str], Optional[bytes]]:
    """Return a fetcher that serves bytes from a dict path → bytes."""
    def fetch(path: str) -> Optional[bytes]:
        v = files.get(path)
        if isinstance(v, str):
            return v.encode("utf-8")
        return v
    return fetch


def make_kobler_golden(tmp: Path) -> Path:
    """Write a minimal kobler-shaped golden to tmp/kobler.golden.spec.yaml."""
    p = tmp / "kobler.golden.spec.yaml"
    p.write_text(yaml.safe_dump({
        "adapter_spec_version": "1.0.0",
        "spec_kind": "prebid-server-adapter",
        "source_language": "go",
        "provenance": {"source": {"resolved_commit": "d7f8515b" + "0" * 32}},
        "meta": {"bidder_name": "kobler", "is_alias": False, "alias_of": None, "disabled": False},
        "bidder_info": {
            "endpoint": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
            "endpoint_compression": "gzip",
            "gvl_vendor_id": 0,
        },
        "bidder_params_sha256": "125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685",
    }))
    return p


class TestFetchers(unittest.TestCase):
    def test_fetch_local_returns_bytes_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "static/bidder-info/kobler.yaml"
            f.parent.mkdir(parents=True)
            f.write_bytes(b"endpoint: foo\n")
            self.assertEqual(b"endpoint: foo\n", sfu.fetch_local(Path(td), "static/bidder-info/kobler.yaml"))

    def test_fetch_local_returns_none_on_missing(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(sfu.fetch_local(Path(td), "static/bidder-info/missing.yaml"))


class TestSha256(unittest.TestCase):
    def test_known_value(self):
        self.assertEqual(
            sfu.compute_sha256(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )


class TestCompareBidderGo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.golden_path = make_kobler_golden(self.tmp_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_match_no_findings(self):
        json_bytes = b"some json bytes"
        sha = sfu.compute_sha256(json_bytes)
        # Update golden to match the synthetic SHA
        with open(self.golden_path) as fp:
            g = yaml.safe_load(fp)
        g["bidder_params_sha256"] = sha
        with open(self.golden_path, "w") as fp:
            yaml.safe_dump(g, fp)

        upstream = {
            "static/bidder-params/kobler.json": json_bytes,
            "static/bidder-info/kobler.yaml": yaml.safe_dump({
                "endpoint": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
                "endpointCompression": "gzip",
                "maintainer": {"email": "x@y.z"},
                "capabilities": {},
                "geoscope": [],
                "gvlVendorID": 0,
            }),
        }
        findings = sfu.compare_bidder_go("kobler", self.golden_path, make_fetcher(upstream))
        self.assertEqual(0, len(findings), f"Expected zero findings, got {findings}")

    def test_sha_drift_emits_fail(self):
        upstream = {
            "static/bidder-params/kobler.json": b"DIVERGENT_BYTES",
            "static/bidder-info/kobler.yaml": yaml.safe_dump({
                "endpoint": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
                "endpointCompression": "gzip",
                "maintainer": {"email": "x@y.z"},
                "capabilities": {},
                "geoscope": [],
                "gvlVendorID": 0,
            }),
        }
        findings = sfu.compare_bidder_go("kobler", self.golden_path, make_fetcher(upstream))
        sha_drifts = [f for f in findings if f.type == "bidder_params_sha_drift"]
        self.assertEqual(1, len(sha_drifts))
        self.assertEqual(sfu.SEVERITY_FAIL, sha_drifts[0].severity)

    def test_endpoint_drift_emits_warn(self):
        json_bytes = b"some json bytes"
        sha = sfu.compute_sha256(json_bytes)
        with open(self.golden_path) as fp:
            g = yaml.safe_load(fp)
        g["bidder_params_sha256"] = sha
        with open(self.golden_path, "w") as fp:
            yaml.safe_dump(g, fp)

        upstream = {
            "static/bidder-params/kobler.json": json_bytes,
            "static/bidder-info/kobler.yaml": yaml.safe_dump({
                "endpoint": "https://NEW-HOST.example.com/v2",  # changed
                "endpointCompression": "gzip",
                "maintainer": {"email": "x@y.z"},
                "capabilities": {},
                "geoscope": [],
                "gvlVendorID": 0,
            }),
        }
        findings = sfu.compare_bidder_go("kobler", self.golden_path, make_fetcher(upstream))
        endpoint_drifts = [f for f in findings if f.type == "endpoint_drift"]
        self.assertEqual(1, len(endpoint_drifts))
        self.assertEqual(sfu.SEVERITY_WARN, endpoint_drifts[0].severity)

    def test_yaml_missing_emits_fail(self):
        upstream = {}  # nothing exists upstream
        findings = sfu.compare_bidder_go("kobler", self.golden_path, make_fetcher(upstream))
        types = {f.type for f in findings}
        self.assertIn("bidder_info_missing", types)
        self.assertIn("bidder_params_missing", types)

    def test_new_yaml_field_emits_fail(self):
        json_bytes = b"some json bytes"
        sha = sfu.compute_sha256(json_bytes)
        with open(self.golden_path) as fp:
            g = yaml.safe_load(fp)
        g["bidder_params_sha256"] = sha
        with open(self.golden_path, "w") as fp:
            yaml.safe_dump(g, fp)

        upstream = {
            "static/bidder-params/kobler.json": json_bytes,
            "static/bidder-info/kobler.yaml": yaml.safe_dump({
                "endpoint": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
                "endpointCompression": "gzip",
                "maintainer": {"email": "x@y.z"},
                "capabilities": {},
                "geoscope": [],
                "gvlVendorID": 0,
                "brand_new_field_phase4_test": "value",  # NEW key — should fire
            }),
        }
        findings = sfu.compare_bidder_go("kobler", self.golden_path, make_fetcher(upstream))
        new_keys = [f for f in findings if f.type == "new_yaml_field"]
        self.assertEqual(1, len(new_keys))
        self.assertEqual(sfu.SEVERITY_FAIL, new_keys[0].severity)


class TestCompareBidderJava(unittest.TestCase):
    def test_default_enabled_drift_emits_warn(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            golden_path = tmp / "kobler.golden.spec.yaml"
            golden_path.write_text(yaml.safe_dump({
                "adapter_spec_version": "1.0.0",
                "spec_kind": "prebid-server-adapter",
                "source_language": "java",
                "meta": {"bidder_name": "kobler", "is_alias": False},
                "bidder_info": {"endpoint": "https://...", "default_enabled": True},
                "bidder_params_sha256": "x" * 64,
            }))
            json_bytes = b"params json"
            upstream = {
                "src/main/resources/static/bidder-params/kobler.json": json_bytes,
                "src/main/resources/bidder-config/kobler.yaml": yaml.safe_dump({
                    "adapters": {
                        "kobler": {
                            "endpoint": "https://...",
                            "enabled": False,  # divergent
                        }
                    }
                }),
            }
            # Update golden sha
            g = yaml.safe_load(golden_path.read_text())
            g["bidder_params_sha256"] = sfu.compute_sha256(json_bytes)
            golden_path.write_text(yaml.safe_dump(g))
            findings = sfu.compare_bidder_java("kobler", golden_path, make_fetcher(upstream))
            drifts = [f for f in findings if f.type == "default_enabled_drift"]
            self.assertEqual(1, len(drifts))
            self.assertEqual(sfu.SEVERITY_WARN, drifts[0].severity)


class TestRender(unittest.TestCase):
    def test_render_md_no_findings(self):
        class Args:
            source_mode = "github-raw"
            ref = "master"
        out = sfu.render_md([], Args())
        self.assertIn("✓ No drift detected", out)

    def test_render_md_with_failures(self):
        f = sfu.Finding("kobler", "go", "bidder_params_sha_drift", sfu.SEVERITY_FAIL,
                         "sha changed", {"golden_sha": "a" * 64})
        class Args:
            source_mode = "github-raw"
            ref = "master"
        out = sfu.render_md([f], Args())
        self.assertIn("Failures (block merges)", out)
        self.assertIn("`kobler`", out)
        self.assertIn("`bidder_params_sha_drift`", out)


class TestDiscovery(unittest.TestCase):
    def test_discover_pinned_finds_corpus(self):
        go, java = sfu.discover_pinned_bidders()
        self.assertGreater(len(go), 5)
        self.assertGreater(len(java), 5)
        self.assertIn("kobler", go)
        self.assertIn("kobler", java)


if __name__ == "__main__":
    unittest.main()
