"""Phase 4.1 unit tests for scripts/sync-from-upstream.py.

Uses synthetic fetcher functions (no network) to exercise the comparison
logic against canned upstream-vs-golden divergences, plus a stubbed `gh`
to exercise the escalation step of `.github/workflows/upstream-sync.yml`.

Every test here was written red first: each one names the behaviour it
guards, and each guarded behaviour was mutated in the source and observed
to redden this file before the fix was kept.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Callable, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "sync-from-upstream.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "upstream-sync.yml"

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


def make_source(files: dict, label: str = "test") -> "sfu.UpstreamSource":
    """A full source: content fetch AND path listing, so glob/exists work."""
    return sfu.UpstreamSource(label, make_fetcher(files), lambda: set(files))


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


def write_golden(tmp: Path, name: str, doc: dict) -> Path:
    p = tmp / f"{name}.golden.spec.yaml"
    p.write_text(yaml.safe_dump(doc))
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

    def test_list_local_paths_walks_checkout_and_skips_git(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "static/bidder-info").mkdir(parents=True)
            (root / "static/bidder-info/kobler.yaml").write_bytes(b"a")
            (root / ".git").mkdir()
            (root / ".git/config").write_bytes(b"b")
            self.assertEqual({"static/bidder-info/kobler.yaml"}, sfu.list_local_paths(root))


class _FakeResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestGithubTreeListing(unittest.TestCase):
    """One recursive tree call per repo is what makes presence checks free.

    Hermetic: `urlopen` is patched, so nothing leaves the machine.
    """

    def _patch(self, payload: dict, capture: list):
        def fake_urlopen(req, timeout=None):
            capture.append(req)
            return _FakeResponse(json.dumps(payload).encode())
        return unittest.mock.patch.object(
            sfu.urllib.request, "urlopen", fake_urlopen)

    def test_returns_blob_paths_only(self):
        payload = {"tree": [
            {"path": "adapters/kobler/kobler.go", "type": "blob"},
            {"path": "adapters/kobler", "type": "tree"},
            {"path": "static/bidder-info/kobler.yaml", "type": "blob"},
        ]}
        with self._patch(payload, []):
            self.assertEqual(
                {"adapters/kobler/kobler.go", "static/bidder-info/kobler.yaml"},
                sfu.list_github_tree("prebid/prebid-server", "master"))

    def test_truncated_listing_is_an_error_not_a_short_path_set(self):
        # A truncated tree would silently shrink the scan set and report
        # every unlisted file as missing.
        with self._patch({"tree": [{"path": "a", "type": "blob"}], "truncated": True}, []):
            with self.assertRaises(sfu.FetchError):
                sfu.list_github_tree("prebid/prebid-server", "master")

    def test_token_is_sent_when_the_environment_supplies_one(self):
        captured: list = []
        with self._patch({"tree": []}, captured):
            with unittest.mock.patch.dict(os.environ, {"GITHUB_TOKEN": "t0ken"}, clear=False):
                sfu.list_github_tree("prebid/prebid-server", "master")
        self.assertEqual("Bearer t0ken", captured[0].get_header("Authorization"))

    def test_no_token_header_when_none_is_available(self):
        captured: list = []
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
        with self._patch({"tree": []}, captured):
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                sfu.list_github_tree("prebid/prebid-server", "master")
        self.assertIsNone(captured[0].get_header("Authorization"))


class TestUpstreamSource(unittest.TestCase):
    def test_failed_listing_degrades_to_per_path_fetch(self):
        def boom():
            raise sfu.FetchError("tree unavailable")
        src = sfu.UpstreamSource("go", make_fetcher({"a.txt": b"x"}), boom)
        self.assertIsNone(src.paths())
        self.assertTrue(src.exists("a.txt"))
        self.assertFalse(src.exists("b.txt"))
        self.assertEqual(["tree unavailable"], src.list_errors)

    def test_listing_makes_presence_checks_cost_no_fetches(self):
        src = make_source({"a.txt": b"x", "b.txt": b"y"})
        self.assertTrue(src.exists("a.txt"))
        self.assertFalse(src.exists("zz.txt"))
        self.assertEqual(0, src.fetch_count)

    def test_content_is_fetched_once_and_cached(self):
        calls: list = []

        def fetch(path):
            calls.append(path)
            return b"x"
        src = sfu.UpstreamSource("go", fetch, lambda: {"a.txt"})
        src.fetch("a.txt")
        src.fetch("a.txt")
        self.assertEqual(["a.txt"], calls)

    def test_prefetch_warms_the_cache_without_changing_results(self):
        files = {f"f{i}.txt": f"body{i}".encode() for i in range(20)}
        src = make_source(files)
        self.assertEqual([], src.prefetch(list(files), max_workers=8))
        self.assertEqual(20, src.fetch_count)
        for path, body in files.items():
            self.assertEqual(body, src.fetch(path))
        self.assertEqual(20, src.fetch_count, "cached reads must not re-fetch")

    def test_glob_is_empty_without_a_listing_backend(self):
        src = sfu.as_source(make_fetcher({"a.json": b"x"}))
        self.assertEqual([], src.glob("*.json"))


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

    def _sync_sha(self, json_bytes: bytes):
        with open(self.golden_path) as fp:
            g = yaml.safe_load(fp)
        g["bidder_params_sha256"] = sfu.compute_sha256(json_bytes)
        with open(self.golden_path, "w") as fp:
            yaml.safe_dump(g, fp)

    def test_clean_match_no_findings(self):
        json_bytes = b"some json bytes"
        self._sync_sha(json_bytes)
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
        self._sync_sha(json_bytes)
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

    def test_whole_bidder_gone_reports_removal_not_two_deletions(self):
        # Defect 5: an upstream where nothing of this bidder survives is a
        # lifecycle event, not two independent file deletions.
        findings = sfu.compare_bidder_go("kobler", self.golden_path, make_fetcher({}))
        self.assertEqual(["bidder_removed_upstream"], [f.type for f in findings])
        self.assertEqual(sfu.SEVERITY_FAIL, findings[0].severity)
        self.assertIsNone(findings[0].detail["successor"])

    def test_single_artifact_deletion_still_reports_that_artifact(self):
        # The lifecycle short-circuit must not swallow an ordinary deletion.
        upstream = {
            "static/bidder-info/kobler.yaml": yaml.safe_dump({
                "endpoint": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
                "endpointCompression": "gzip", "gvlVendorID": 0,
            }),
        }
        findings = sfu.compare_bidder_go("kobler", self.golden_path, make_source(upstream))
        self.assertIn("bidder_params_missing", {f.type for f in findings})
        self.assertNotIn("bidder_removed_upstream", {f.type for f in findings})

    def test_new_yaml_field_emits_fail(self):
        json_bytes = b"some json bytes"
        self._sync_sha(json_bytes)
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


# ---------------------------------------------------------------------------
# Defect 2 — the tracked-field tables must be wired in, not decorative
# ---------------------------------------------------------------------------

class TestTrackedFieldTables(unittest.TestCase):
    """Every FieldSpec must reach production and be able to fire.

    A table that is declared and never referenced is exactly the failure
    this replaces: `modifying-vast-xml-allowed`, `ortb-version` and
    `gvl-vendor-id` were advertised for years and never read.
    """

    GO_UPSTREAM_SAMPLE = {
        "endpoint": "https://e.example/bid",
        "endpointCompression": "gzip",
        "gvlVendorID": 42,
        "modifyingVastXmlAllowed": True,
        "openrtb": {"version": "2.6"},
        "disabled": True,
        "aliasOf": "parentbidder",
    }
    JAVA_UPSTREAM_SAMPLE = {
        "endpoint": "https://e.example/bid",
        "endpoint-compression": "gzip",
        "meta-info": {"vendor-id": 42},
        "modifying-vast-xml-allowed": True,
        "ortb-version": "2.6",
        "enabled": False,
    }

    def _golden_matching(self, specs, upstream):
        """A golden whose tracked values equal the upstream sample."""
        golden: dict = {}
        for spec in specs:
            value = None
            for key in spec.upstream_keys:
                value = sfu._dotted(upstream, key)
                if value is not None:
                    break
            cur = golden
            for k in spec.golden_keys[:-1]:
                cur = cur.setdefault(k, {})
            cur[spec.golden_keys[-1]] = value
        return golden

    def _assert_table_live(self, specs, upstream, where):
        golden = self._golden_matching(specs, upstream)
        clean = sfu.compare_fields("b", "go", golden, upstream, specs, where)
        self.assertEqual([], clean, f"baseline must be clean, got {clean}")
        for spec in specs:
            mutated = json.loads(json.dumps(golden))
            cur = mutated
            for k in spec.golden_keys[:-1]:
                cur = cur.setdefault(k, {})
            cur[spec.golden_keys[-1]] = "__SEEDED_DIVERGENCE__"
            found = sfu.compare_fields("b", "go", mutated, upstream, specs, where)
            self.assertEqual(
                [f"{spec.name}_drift"], [f.type for f in found],
                f"FieldSpec {spec.name!r} is declared but never fires — dead entry")

    def test_every_go_field_spec_is_live(self):
        self._assert_table_live(sfu.GO_BIDDER_INFO_FIELDS,
                                self.GO_UPSTREAM_SAMPLE, "bidder_info")

    def test_every_java_field_spec_is_live(self):
        self._assert_table_live(sfu.JAVA_BIDDER_CONFIG_FIELDS,
                                self.JAVA_UPSTREAM_SAMPLE, "adapters.b")

    def test_go_table_covers_the_fields_the_docstring_advertises(self):
        names = {s.name for s in sfu.GO_BIDDER_INFO_FIELDS}
        self.assertLessEqual(
            {"endpoint", "endpoint_compression", "gvl_vendor_id",
             "modifying_vast_xml_allowed", "disabled"}, names)

    def test_java_table_covers_the_fields_the_docstring_advertises(self):
        names = {s.name for s in sfu.JAVA_BIDDER_CONFIG_FIELDS}
        self.assertLessEqual(
            {"endpoint", "endpoint_compression", "gvl_vendor_id",
             "modifying_vast_xml_allowed", "ortb_version", "default_enabled"}, names)

    def test_modifying_vast_xml_allowed_drift_is_reported_go(self):
        # Rule 49 turns on this field; it was never compared before.
        golden = {"bidder_info": {"modifying_vast_xml_allowed": False}}
        upstream = {"modifyingVastXmlAllowed": True}
        found = sfu.compare_fields("b", "go", golden, upstream,
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertEqual(["modifying_vast_xml_allowed_drift"], [f.type for f in found])

    def test_ortb_version_omission_is_reported_go(self):
        # Golden says null, upstream declares 2.6 — the omission class that
        # went unreported for sixteen weeks.
        golden = {"bidder_info": {"ortb_version": None}}
        upstream = {"openrtb": {"version": 2.6}}
        found = sfu.compare_fields("b", "go", golden, upstream,
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertEqual(["ortb_version_drift"], [f.type for f in found])

    def test_ortb_version_quoting_is_not_drift(self):
        # Upstream writes `version: 2.6` (YAML float); goldens record "2.6".
        golden = {"bidder_info": {"ortb_version": "2.6"}}
        upstream = {"openrtb": {"version": 2.6}}
        self.assertEqual([], sfu.compare_fields("b", "go", golden, upstream,
                                                sfu.GO_BIDDER_INFO_FIELDS, "bidder_info"))

    def test_scalar_equal_keeps_booleans_strict(self):
        self.assertTrue(sfu._scalar_equal("2.6", 2.6))
        self.assertTrue(sfu._scalar_equal(52, "52"))
        self.assertFalse(sfu._scalar_equal(True, 1))
        self.assertFalse(sfu._scalar_equal(False, 0))
        self.assertFalse(sfu._scalar_equal(2.6, 2.7))
        self.assertFalse(sfu._scalar_equal(None, "x"))

    def test_gvl_vendor_id_absent_upstream_reads_as_zero(self):
        golden = {"bidder_info": {"gvl_vendor_id": 0}}
        self.assertEqual([], sfu.compare_fields("b", "go", golden, {},
                                                sfu.GO_BIDDER_INFO_FIELDS, "bidder_info"))
        golden = {"bidder_info": {"gvl_vendor_id": 14}}
        found = sfu.compare_fields("b", "go", golden, {},
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertEqual(["gvl_vendor_id_drift"], [f.type for f in found])

    def test_java_alias_inherits_parent_section(self):
        # 152media lives at adapters.adkernel.aliases.152media and inherits
        # everything else. Reading `adapters.152media` yields {} and would
        # report every inherited field as drift.
        doc = {"adapters": {"adkernel": {
            "endpoint": "http://pbs.adksrv.com/hb?zone={ZoneId}",
            "endpoint-compression": "gzip",
            "meta-info": {"vendor-id": 14},
            "aliases": {"152media": {"meta-info": {"vendor-id": 1111}}},
        }}}
        golden = {"meta": {"is_alias": True, "alias_of": "adkernel"}}
        section = sfu.resolve_java_adapter_section(doc, "152media", golden)
        self.assertEqual("http://pbs.adksrv.com/hb?zone={ZoneId}", section["endpoint"])
        self.assertEqual("gzip", section["endpoint-compression"])
        self.assertEqual(1111, section["meta-info"]["vendor-id"])   # alias override wins
        self.assertNotIn("aliases", section)

    def test_java_alias_tilde_inherit_takes_parent_values(self):
        doc = {"adapters": {"adkernel": {
            "endpoint": "http://p/hb", "meta-info": {"vendor-id": 14},
            "aliases": {"152media": None},
        }}}
        golden = {"meta": {"is_alias": True, "alias_of": "adkernel"}}
        section = sfu.resolve_java_adapter_section(doc, "152media", golden)
        self.assertEqual(14, section["meta-info"]["vendor-id"])


# ---------------------------------------------------------------------------
# Defect 3 — the scan set must be materially wider than two globs
# ---------------------------------------------------------------------------

GO_WIDE_GOLDEN = {
    "meta": {"bidder_name": "kobler", "is_alias": False, "alias_of": None},
    "bidder_info": {"endpoint": "https://e/bid", "gvl_vendor_id": 0},
    "bidder_params_sha256": "a" * 64,
    "cross_language": {"go_artifacts": {
        "bidder_dir": "adapters/kobler/",
        "bidder_constant": "openrtb_ext.BidderKobler",
    }},
    "code": {"file_layout": {"files": [
        {"name": "kobler.go", "role": "implementation"},
        {"name": "models.go", "role": "support"},
    ]}},
    "params": {"ext_struct": {"file": "openrtb_ext/imp_kobler.go"},
               "params_test": {"file": "adapters/kobler/params_test.go"}},
    "tests": {"test_root_directory": "koblertest", "fixture_inventory": {
        "exemplary": [{"filename": "banner.json", "sha256": "b" * 64}],
        "supplemental": ["status-204"],
    }},
}

JAVA_WIDE_GOLDEN = {
    "meta": {"bidder_name": "kobler", "is_alias": False, "alias_of": None},
    "bidder_info": {"endpoint": "https://e/bid"},
    "bidder_params_sha256": "a" * 64,
    "cross_language": {"java_artifacts": {
        "bidder_dir": "src/main/java/org/prebid/server/bidder/kobler/",
        "yaml_path": "src/main/resources/bidder-config/kobler.yaml",
    }},
    "code": {"file_layout": {"files": [
        {"name": "KoblerBidder.java"}, {"name": "model/"},
    ]}},
    "registry": {"test_application_properties": {
        "file": "src/test/resources/org/prebid/server/it/test-application.properties",
        "entries": ["adapters.kobler.enabled=true"]}},
    "tests": {"fixture_inventory": {"integration": [
        {"filename": "test-kobler-bid-request.json", "sha256": "c" * 64}]}},
}


class TestNoDeadModuleConstants(unittest.TestCase):
    """No module-level constant may be declared and never read.

    `GO_BIDDER_INFO_FIELDS` and `JAVA_BIDDER_CONFIG_FIELDS` sat unreferenced
    while the module docstring claimed the script tracked those fields. This
    is the guard that would have caught it.
    """

    def test_every_module_constant_is_referenced(self):
        import ast
        tree = ast.parse(SCRIPT_PATH.read_text())
        declared: dict = {}
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
            for t in targets:
                if t.id.isupper() or (t.id.startswith("_") and t.id.upper() == t.id):
                    declared.setdefault(t.id, node.lineno)
        loads = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                loads.add(node.id)
        dead = sorted(n for n in declared if n not in loads)
        self.assertEqual(
            [], dead,
            f"declared but never read: {[(n, declared[n]) for n in dead]}")


class TestDeriveWatchedPaths(unittest.TestCase):
    def test_core_artifact_templates_are_the_source_of_truth(self):
        # Literals, not `template.format(...)` — re-deriving production's own
        # expression from production's own constant proves nothing.
        for template in sfu.GO_FILES_PER_BIDDER + sfu.JAVA_FILES_PER_BIDDER:
            self.assertIn(template, sfu.CORE_ARTIFACT_ROLES)
        self.assertEqual(
            ["src/main/resources/bidder-config/kobler.yaml",
             "src/main/resources/static/bidder-params/kobler.json"],
            [w.path for w in sfu.derive_watched_paths("kobler", {}, "java", sfu.TIER_CORE)[0]])
        self.assertEqual(
            ["static/bidder-info/kobler.yaml", "static/bidder-params/kobler.json"],
            [w.path for w in sfu.derive_watched_paths("kobler", {}, "go", sfu.TIER_CORE)[0]])

    def test_java_params_path_override_beats_the_template(self):
        golden = {"cross_language": {"java_artifacts": {
            "bidder_params_path": "src/main/resources/static/bidder-params/emx_digital.json"}}}
        watched, _ = sfu.derive_watched_paths("emxdigital", golden, "java", sfu.TIER_CORE)
        paths = [w.path for w in watched]
        self.assertIn("src/main/resources/static/bidder-params/emx_digital.json", paths)
        self.assertNotIn("src/main/resources/static/bidder-params/emxdigital.json", paths)

    def test_core_tier_is_the_legacy_two_globs(self):
        watched, _ = sfu.derive_watched_paths("kobler", GO_WIDE_GOLDEN, "go", sfu.TIER_CORE)
        self.assertEqual(
            ["static/bidder-info/kobler.yaml", "static/bidder-params/kobler.json"],
            [w.path for w in watched])

    def test_source_tier_adds_declared_source_files(self):
        watched, _ = sfu.derive_watched_paths("kobler", GO_WIDE_GOLDEN, "go", sfu.TIER_SOURCE)
        paths = {w.path for w in watched}
        self.assertIn("adapters/kobler/kobler.go", paths)
        self.assertIn("adapters/kobler/models.go", paths)
        self.assertIn("openrtb_ext/imp_kobler.go", paths)
        self.assertIn("adapters/kobler/params_test.go", paths)

    def test_source_tier_adds_go_registration_sites(self):
        watched, _ = sfu.derive_watched_paths("kobler", GO_WIDE_GOLDEN, "go", sfu.TIER_SOURCE)
        reg = {w.path: w for w in watched if w.kind == "registration"}
        self.assertIn(sfu.GO_BIDDER_REGISTRY, reg)
        self.assertIn(sfu.GO_BUILDER_REGISTRY, reg)
        self.assertEqual(["BidderKobler "], reg[sfu.GO_BIDDER_REGISTRY].detail["entries"])
        self.assertEqual(["openrtb_ext.BidderKobler:"], reg[sfu.GO_BUILDER_REGISTRY].detail["entries"])

    def test_source_tier_adds_java_registration_entries(self):
        watched, _ = sfu.derive_watched_paths("kobler", JAVA_WIDE_GOLDEN, "java", sfu.TIER_SOURCE)
        reg = [w for w in watched if w.kind == "registration"]
        self.assertEqual(1, len(reg))
        self.assertEqual(["adapters.kobler.enabled=true"], reg[0].detail["entries"])

    def test_full_tier_adds_fixtures_with_and_without_sha(self):
        watched, _ = sfu.derive_watched_paths("kobler", GO_WIDE_GOLDEN, "go", sfu.TIER_FULL)
        fixtures = {w.path: w for w in watched if w.kind == "fixture"}
        self.assertEqual("sha", fixtures["adapters/kobler/koblertest/exemplary/banner.json"].check)
        # A bare stem with no recorded digest is still presence-checked.
        self.assertEqual("presence",
                         fixtures["adapters/kobler/koblertest/supplemental/status-204.json"].check)

    def test_java_fixture_paths_resolve_under_the_it_resource_root(self):
        watched, _ = sfu.derive_watched_paths("kobler", JAVA_WIDE_GOLDEN, "java", sfu.TIER_FULL)
        paths = {w.path for w in watched}
        self.assertIn(sfu.JAVA_IT_RESOURCE_ROOT + "openrtb2/kobler/test-kobler-bid-request.json",
                      paths)

    def test_folder_qualified_fixture_names_are_not_double_prefixed(self):
        golden = json.loads(json.dumps(JAVA_WIDE_GOLDEN))
        golden["tests"]["fixture_inventory"]["integration"] = [
            {"filename": "openrtb2/generic_core_functionality/test-generic-bid-request.json",
             "sha256": "d" * 64}]
        watched, _ = sfu.derive_watched_paths("generic", golden, "java", sfu.TIER_FULL)
        fixtures = [w.path for w in watched if w.kind == "fixture"]
        self.assertEqual(
            [sfu.JAVA_IT_RESOURCE_ROOT
             + "openrtb2/generic_core_functionality/test-generic-bid-request.json"],
            fixtures)

    def test_prose_placeholder_is_not_treated_as_a_path(self):
        golden = json.loads(json.dumps(GO_WIDE_GOLDEN))
        golden["tests"]["fixture_inventory"]["supplemental"] = [
            {"filename": "40 supplemental fixtures (error paths)", "sha256": "pending"}]
        watched, unresolvable = sfu.derive_watched_paths("kobler", golden, "go", sfu.TIER_FULL)
        self.assertFalse([w for w in watched if "40 supplemental" in w.path])
        self.assertEqual(1, len(unresolvable))

    def test_directory_entry_is_recorded_as_unresolvable_not_watched(self):
        watched, unresolvable = sfu.derive_watched_paths(
            "kobler", JAVA_WIDE_GOLDEN, "java", sfu.TIER_SOURCE)
        self.assertFalse([w for w in watched if w.path.endswith("model")])
        self.assertTrue(any("model/" in u for u in unresolvable))

    def test_real_corpus_scan_set_is_materially_wider_than_the_legacy_globs(self):
        """Coverage floor over the shipped goldens.

        The legacy surface was 2 paths per bidder/language pair (84 across
        the corpus). This asserts the derived surface stays several times
        that; it reddens the moment the derivation silently narrows.
        """
        go, java = sfu.discover_pinned_bidders()
        legacy = 0
        full = 0
        for lang, corpus in (("go", go), ("java", java)):
            for bidder, path in corpus.items():
                golden = yaml.safe_load(path.read_text()) or {}
                legacy += len(sfu.derive_watched_paths(bidder, golden, lang, sfu.TIER_CORE)[0])
                full += len(sfu.derive_watched_paths(bidder, golden, lang, sfu.TIER_FULL)[0])
        self.assertEqual(84, legacy, "legacy surface changed; update the floor deliberately")
        self.assertGreaterEqual(full, 500, f"derived surface collapsed to {full} paths")


class TestWidenedChecks(unittest.TestCase):
    """The wider scan set must actually produce findings, not just paths."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.golden_path = write_golden(self.tmp_path, "kobler", GO_WIDE_GOLDEN)
        self.upstream = {
            "static/bidder-info/kobler.yaml": yaml.safe_dump(
                {"endpoint": "https://e/bid", "gvlVendorID": 0}),
            "static/bidder-params/kobler.json": b"params",
            "adapters/kobler/kobler.go": b"package kobler\n",
            "adapters/kobler/models.go": b"package kobler\n",
            "adapters/kobler/params_test.go": b"package kobler\n",
            "openrtb_ext/imp_kobler.go": b"package openrtb_ext\n",
            "adapters/kobler/koblertest/exemplary/banner.json": b"fixture",
            "adapters/kobler/koblertest/supplemental/status-204.json": b"fixture",
            sfu.GO_BIDDER_REGISTRY: b"\tBidderKobler            BidderName = \"kobler\"\n",
            sfu.GO_BUILDER_REGISTRY: b"\t\topenrtb_ext.BidderKobler:            kobler.Builder,\n",
        }
        g = yaml.safe_load(self.golden_path.read_text())
        g["bidder_params_sha256"] = sfu.compute_sha256(b"params")
        g["tests"]["fixture_inventory"]["exemplary"][0]["sha256"] = sfu.compute_sha256(b"fixture")
        self.golden_path.write_text(yaml.safe_dump(g))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, upstream=None):
        return sfu.compare_bidder_go("kobler", self.golden_path,
                                     make_source(upstream or self.upstream),
                                     tier=sfu.TIER_FULL)

    def test_baseline_is_clean(self):
        self.assertEqual([], self._run())

    def test_deleted_adapter_source_file_is_reported(self):
        upstream = dict(self.upstream)
        del upstream["adapters/kobler/models.go"]
        found = [f for f in self._run(upstream) if f.type == "source_file_missing"]
        self.assertEqual(1, len(found))
        self.assertEqual("adapters/kobler/models.go", found[0].detail["path"])
        self.assertEqual("code.file_layout.files[]", found[0].detail["origin"])

    def test_deregistered_bidder_constant_is_reported(self):
        upstream = dict(self.upstream)
        upstream[sfu.GO_BUILDER_REGISTRY] = b"\t\topenrtb_ext.BidderOther: other.Builder,\n"
        found = [f for f in self._run(upstream) if f.type == "registration_entry_missing"]
        self.assertEqual(1, len(found))
        self.assertEqual(sfu.SEVERITY_FAIL, found[0].severity)
        self.assertEqual(["openrtb_ext.BidderKobler:"], found[0].detail["missing_entries"])

    def test_fixture_content_drift_is_reported(self):
        upstream = dict(self.upstream)
        upstream["adapters/kobler/koblertest/exemplary/banner.json"] = b"CHANGED"
        found = [f for f in self._run(upstream) if f.type == "fixture_content_drift"]
        self.assertEqual(1, len(found))
        self.assertEqual(sfu.SEVERITY_WARN, found[0].severity)

    def test_deleted_fixture_is_reported(self):
        upstream = dict(self.upstream)
        del upstream["adapters/kobler/koblertest/exemplary/banner.json"]
        found = [f for f in self._run(upstream) if f.type == "fixture_file_missing"]
        self.assertEqual(1, len(found))

    def test_core_tier_sees_none_of_it(self):
        """The legacy surface is blind to every one of the above."""
        upstream = dict(self.upstream)
        del upstream["adapters/kobler/models.go"]
        del upstream["adapters/kobler/koblertest/exemplary/banner.json"]
        upstream[sfu.GO_BUILDER_REGISTRY] = b"nothing here\n"
        findings = sfu.compare_bidder_go("kobler", self.golden_path,
                                         make_source(upstream), tier=sfu.TIER_CORE)
        self.assertEqual([], findings)


# ---------------------------------------------------------------------------
# Defect 5 — rename and removal get their own vocabulary
# ---------------------------------------------------------------------------

class TestLifecycleVocabulary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_byte_identical_params_rename_is_not_a_deletion(self):
        # emxdigital: emx_digital.json -> emxdigital.json, same bytes.
        params = b'{"title": "EMX params"}'
        golden = {
            "meta": {"bidder_name": "emxdigital", "is_alias": False},
            "bidder_info": {"endpoint": "https://e/bid"},
            "bidder_params_sha256": sfu.compute_sha256(params),
            "cross_language": {"java_artifacts": {
                "bidder_params_path": "src/main/resources/static/bidder-params/emx_digital.json",
                "yaml_path": "src/main/resources/bidder-config/emxdigital.yaml"}},
        }
        gp = write_golden(self.tmp_path, "emxdigital", golden)
        upstream = {
            "src/main/resources/static/bidder-params/emxdigital.json": params,
            "src/main/resources/bidder-config/emxdigital.yaml": yaml.safe_dump(
                {"adapters": {"emxdigital": {"endpoint": "https://e/bid"}}}),
        }
        findings = sfu.compare_bidder_java("emxdigital", gp, make_source(upstream))
        self.assertEqual(["bidder_params_renamed_upstream"], [f.type for f in findings])
        detail = findings[0].detail
        self.assertTrue(detail["content_identical"])
        self.assertEqual("src/main/resources/static/bidder-params/emxdigital.json",
                         detail["candidate"])
        self.assertNotIn("missing", findings[0].message)

    def test_renamed_bidder_names_its_successor(self):
        # rubicon -> magnite: every rubicon artifact is gone, and magnite.yaml
        # declares rubicon as one of its aliases.
        golden = {
            "meta": {"bidder_name": "rubicon", "is_alias": False},
            "bidder_info": {"endpoint": "https://REGION.rubiconproject.com"},
            "bidder_params_sha256": "e" * 64,
            "cross_language": {"java_artifacts": {
                "bidder_dir": "src/main/java/org/prebid/server/bidder/rubicon/",
                "yaml_path": "src/main/resources/bidder-config/rubicon.yaml"}},
            "code": {"file_layout": {"files": [{"name": "RubiconBidder.java"}]}},
            # The IT fixture is WATCHED and it SURVIVED the rename. Scanning
            # at the full tier is what makes that fact load-bearing: if test
            # resources counted as implementation artifacts, the surviving
            # fixture would suppress the lifecycle finding and the run would
            # report thirty individual deletions instead.
            "tests": {"fixture_inventory": {"integration": [
                {"filename": "test-rubicon-bid-request.json",
                 "sha256": sfu.compute_sha256(b"{}")}]}},
        }
        gp = write_golden(self.tmp_path, "rubicon", golden)
        upstream = {
            "src/main/resources/bidder-config/magnite.yaml": yaml.safe_dump(
                {"adapters": {"magnite": {
                    "endpoint": "https://REGION.rubiconproject.com",
                    "aliases": {"rubicon": {"enabled": False}}}}}),
            "src/main/resources/static/bidder-params/magnite.json": b"{}",
            sfu.JAVA_IT_RESOURCE_ROOT + "openrtb2/rubicon/test-rubicon-bid-request.json": b"{}",
        }
        watched, _ = sfu.derive_watched_paths("rubicon", golden, "java", sfu.TIER_FULL)
        self.assertIn(sfu.JAVA_IT_RESOURCE_ROOT + "openrtb2/rubicon/test-rubicon-bid-request.json",
                      {w.path for w in watched})
        findings = sfu.compare_bidder_java("rubicon", gp, make_source(upstream),
                                           tier=sfu.TIER_FULL)
        self.assertEqual(["bidder_renamed_upstream"], [f.type for f in findings])
        self.assertEqual("magnite", findings[0].detail["successor"])
        self.assertEqual(3, findings[0].detail["vanished_count"])
        self.assertNotIn("fixture", str(findings[0].detail["vanished_paths"]))

    def test_removed_bidder_without_successor_says_removed(self):
        golden = {
            "meta": {"bidder_name": "gone", "is_alias": False},
            "bidder_info": {"endpoint": "https://e/bid"},
            "bidder_params_sha256": "e" * 64,
            "cross_language": {"java_artifacts": {
                "bidder_dir": "src/main/java/org/prebid/server/bidder/gone/",
                "yaml_path": "src/main/resources/bidder-config/gone.yaml"}},
            "code": {"file_layout": {"files": [{"name": "GoneBidder.java"}]}},
        }
        gp = write_golden(self.tmp_path, "gone", golden)
        upstream = {"src/main/resources/bidder-config/other.yaml": yaml.safe_dump(
            {"adapters": {"other": {"endpoint": "https://o"}}})}
        findings = sfu.compare_bidder_java("gone", gp, make_source(upstream),
                                           tier=sfu.TIER_SOURCE)
        self.assertEqual(["bidder_removed_upstream"], [f.type for f in findings])
        self.assertIsNone(findings[0].detail["successor"])

    def test_alias_child_is_never_reported_as_removed(self):
        # 152media owns no bidder-config and no bidder-params of its own.
        golden = {
            "meta": {"bidder_name": "152media", "is_alias": True, "alias_of": "adkernel"},
            "bidder_info": {"endpoint": "http://p/hb", "gvl_vendor_id": 14},
            "bidder_params_sha256": "e" * 64,
            "cross_language": {"java_artifacts": {
                "yaml_path": "src/main/resources/bidder-config/adkernel.yaml"}},
        }
        gp = write_golden(self.tmp_path, "152media", golden)
        upstream = {"src/main/resources/bidder-config/adkernel.yaml": yaml.safe_dump(
            {"adapters": {"adkernel": {"endpoint": "http://p/hb",
                                       "meta-info": {"vendor-id": 14},
                                       "aliases": {"152media": None}}}})}
        findings = sfu.compare_bidder_java("152media", gp, make_source(upstream))
        self.assertEqual([], [f.type for f in findings])

    def test_source_rename_does_not_match_an_unrelated_sibling(self):
        """A deleted `params_test.go` is not a rename of `adkernelAdn.go`.

        The bidder-token fallback only applies to artifacts named after the
        bidder; letting it reach ordinary source files produced a confident
        false rename for every package whose implementation file shares the
        directory name.
        """
        source = make_source({"adapters/adkernelAdn/adkernelAdn.go": b"package x\n"})
        self.assertIsNone(sfu.find_relocated_artifact(
            source, "adapters/adkernelAdn/params_test.go", "adkernelAdn", None,
            match_bidder_token=False))
        # The same call WITH the fallback is exactly the false positive.
        self.assertIsNotNone(sfu.find_relocated_artifact(
            source, "adapters/adkernelAdn/params_test.go", "adkernelAdn", None,
            match_bidder_token=True))

    def test_lifecycle_types_are_distinct_from_data_drift_types(self):
        lifecycle = {"bidder_renamed_upstream", "bidder_removed_upstream",
                     "bidder_params_renamed_upstream", "artifact_renamed_upstream"}
        deletion = {"bidder_params_missing", "bidder_config_missing",
                    "bidder_info_missing", "source_file_missing",
                    "fixture_file_missing"}
        data = {f"{s.name}_drift" for s in sfu.GO_BIDDER_INFO_FIELDS}
        self.assertEqual(set(), lifecycle & deletion)
        self.assertEqual(set(), lifecycle & data)


# ---------------------------------------------------------------------------
# Defect 4 — the report must state the real scan set
# ---------------------------------------------------------------------------

class Args:
    source_mode = "github-raw"
    ref = "master"


def make_scan(pairs, paths=(), skipped=(), tier="full", shard=None, unresolvable=()):
    return sfu.ScanSet(pairs=list(pairs), skipped=list(skipped), paths=list(paths),
                       tier=tier, shard=shard, unresolvable=list(unresolvable))


class TestRender(unittest.TestCase):
    def test_render_md_no_findings(self):
        out = sfu.render_md([], Args())
        self.assertIn("✓ No drift detected", out)

    def test_render_md_with_failures(self):
        f = sfu.Finding("kobler", "go", "bidder_params_sha_drift", sfu.SEVERITY_FAIL,
                        "sha changed", {"golden_sha": "a" * 64})
        out = sfu.render_md([f], Args())
        self.assertIn("Failures (block merges)", out)
        self.assertIn("`kobler`", out)
        self.assertIn("`bidder_params_sha_drift`", out)

    def test_clean_run_reports_the_pairs_it_scanned_not_zero(self):
        """A clean run over 42 pairs must print 42, not 0.

        The old line was `len(set((f.bidder, f.language) for f in findings))`
        — pairs WITH FINDINGS — so it moved inversely with health and a
        fully clean run advertised "0 pairs scanned".
        """
        pairs = [(f"b{i}", "go") for i in range(42)]
        out = sfu.render_md([], Args(), make_scan(pairs))
        self.assertIn("Pairs scanned: **42**", out)
        self.assertNotIn("Pairs scanned: **0**", out)

    def test_scan_set_is_not_derived_from_findings(self):
        pairs = [(f"b{i}", "go") for i in range(42)]
        findings = [sfu.Finding("b1", "go", "endpoint_drift", sfu.SEVERITY_WARN, "m", {})]
        out = sfu.render_md(findings, Args(), make_scan(pairs))
        self.assertIn("Pairs scanned: **42**", out)
        self.assertIn("Findings emitted: **1** over 1 pair(s).", out)

    def test_report_counts_watched_paths_by_check(self):
        paths = [sfu.WatchedPath("a", "source", "presence", "o"),
                 sfu.WatchedPath("b", "fixture", "sha", "o"),
                 sfu.WatchedPath("c", "bidder_info", "field", "o")]
        out = sfu.render_md([], Args(), make_scan([("k", "go")], paths))
        self.assertIn("Upstream paths watched: **3**", out)
        self.assertIn("1 field", out)
        self.assertIn("1 presence", out)
        self.assertIn("1 sha", out)

    def test_report_names_skipped_pairs(self):
        out = sfu.render_md([], Args(),
                            make_scan([("k", "go")], skipped=[("r", "java", "no checkout")]))
        self.assertIn("Pairs discovered but NOT scanned: **1**", out)
        self.assertIn("no checkout", out)

    def test_empty_scan_set_is_not_reported_as_an_all_clear(self):
        out = sfu.render_md([], Args(), make_scan([]))
        self.assertIn("The scan set is empty. This report is not an all-clear.", out)

    def test_report_states_tier_and_shard(self):
        out = sfu.render_md([], Args(), make_scan([("k", "go")], tier="source", shard="2/4"))
        self.assertIn("scan tier `source`", out)
        self.assertIn("shard `2/4`", out)


class TestSharding(unittest.TestCase):
    def test_shard_partitions_without_overlap_or_loss(self):
        pairs = [(f"b{i}", "go") for i in range(10)]
        shards = [sfu.apply_shard(pairs, (i, 3)) for i in (1, 2, 3)]
        flat = [p for s in shards for p in s]
        self.assertEqual(sorted(pairs), sorted(flat))
        self.assertEqual(len(flat), len(set(flat)))

    def test_shard_spec_parsing(self):
        self.assertEqual((2, 4), sfu.parse_shard("2/4"))
        self.assertIsNone(sfu.parse_shard(None))
        for bad in ("0/4", "5/4", "x", "1/0", "-1/2"):
            with self.assertRaises(ValueError, msg=bad):
                sfu.parse_shard(bad)


class TestMainExitCodes(unittest.TestCase):
    """Zero inputs is an instrument failure, not a clean verdict."""

    def test_local_mode_without_any_checkout_exits_3(self):
        with tempfile.TemporaryDirectory() as td:
            rc = sfu.main(["--source-mode=local", f"--out-dir={td}", "--quiet"])
        self.assertEqual(3, rc)

    def test_unknown_bidder_exits_3(self):
        with tempfile.TemporaryDirectory() as td:
            rc = sfu.main(["--source-mode=local", "--go-checkout=" + td,
                           "--bidder=definitely-not-a-bidder", f"--out-dir={td}", "--quiet"])
        self.assertEqual(3, rc)

    def test_bad_shard_spec_exits_3(self):
        with tempfile.TemporaryDirectory() as td:
            rc = sfu.main(["--source-mode=local", "--go-checkout=" + td,
                           "--shard=9/4", f"--out-dir={td}", "--quiet"])
        self.assertEqual(3, rc)

    def test_shard_that_selects_nothing_exits_3(self):
        # A shard index that lands on an empty slice must not read as clean.
        with tempfile.TemporaryDirectory() as td:
            rc = sfu.main(["--source-mode=local", "--go-checkout=" + td,
                           "--bidder=kobler", "--shard=3/3",
                           f"--out-dir={td}", "--quiet"])
        self.assertEqual(3, rc)

    def test_json_report_records_the_scan_set(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            sfu.main(["--source-mode=local", "--go-checkout=" + td,
                      "--bidder=kobler", "--scan-tier=core",
                      f"--out-dir={out}", "--quiet"])
            report = json.loads((out / "drift-report.json").read_text())
        self.assertEqual(1, report["scan_set"]["pairs_scanned"])
        self.assertEqual(["kobler/go"], report["scan_set"]["pairs_scanned_list"])
        self.assertEqual(2, report["scan_set"]["paths_watched"])
        self.assertIn("kobler", str(report["scan_set"]["pairs_skipped"]))
        self.assertEqual(report["finding_count"], len(report["findings"]))


class TestDiscovery(unittest.TestCase):
    def test_discover_pinned_finds_corpus(self):
        go, java = sfu.discover_pinned_bidders()
        self.assertGreater(len(go), 5)
        self.assertGreater(len(java), 5)
        self.assertIn("kobler", go)
        self.assertIn("kobler", java)


# ---------------------------------------------------------------------------
# Defect 1 — the workflow must be able to escalate
# ---------------------------------------------------------------------------

GH_STUB = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["GH_LOG"], "a") as fp:
    fp.write(json.dumps(sys.argv[1:]) + "\n")
args = sys.argv[1:]
existing = os.environ.get("STUB_EXISTING", "none")
if args[:1] == ["api"]:
    target = [a for a in args if a.startswith("repos/")]
    if target and "/issues/" in target[0]:
        print("open" if existing == "open" else "closed")
    elif existing != "none":
        print("4242")
sys.exit(0)
'''

_EXPR_SUBS = {
    r"\$\{\{\s*github\.token\s*\}\}": "stub-token",
    r"\$\{\{\s*github\.server_url\s*\}\}": "https://github.com",
    r"\$\{\{\s*github\.repository\s*\}\}": "prebid/prebid-agent-skills",
    r"\$\{\{\s*github\.run_id\s*\}\}": "99",
}


def _substitute(text: str, exit_code: str, claims: str = "0", refs: str = "0",
                baseline: str = "0", fixtures: str = "0") -> str:
    """Render a step's shell body with the step outputs it reads.

    `claims`, `refs`, `baseline` and `fixtures` default to "0" so the many callers
    that only care about the sync exit keep working. An EMPTY string is a meaningful value,
    not a default: GitHub renders an unset step output as the empty string, which
    is what a step that died before its `echo` produces.
    """
    text = re.sub(r"\$\{\{\s*steps\.sync\.outputs\.exit\s*\}\}", exit_code, text)
    text = re.sub(r"\$\{\{\s*steps\.claims\.outputs\.exit\s*\}\}", claims, text)
    text = re.sub(r"\$\{\{\s*steps\.refs\.outputs\.exit\s*\}\}", refs, text)
    text = re.sub(r"\$\{\{\s*steps\.baseline\.outputs\.exit\s*\}\}", baseline, text)
    text = re.sub(r"\$\{\{\s*steps\.fixtures\.outputs\.exit\s*\}\}", fixtures, text)
    for pat, val in _EXPR_SUBS.items():
        text = re.sub(pat, val, text)
    return text


class TestGoldenKeysAlt(unittest.TestCase):
    """A field the reader may record in either of two documented places.

    `read-bidder-info/SKILL.md` tells the Go reader that when `openrtb:` is a
    nested map it should preserve the nested layout at
    `bidder_info.yaml_extra_fields.openrtb.version` and leave top-level
    `ortb_version: null`. Three goldens (elementaltv, msft, optidigital) follow
    that policy exactly and were reported as drifting against upstream files they
    record faithfully, because this comparison read only the top-level field.
    freewheelssp uses the other documented style and never drifted, which is why
    the defect looked bidder-specific.
    """

    def test_nested_extra_fields_location_satisfies_the_comparison(self):
        golden = {"bidder_info": {"ortb_version": None,
                                  "yaml_extra_fields": {"openrtb": {"version": 2.6}}}}
        found = sfu.compare_fields("b", "go", golden, {"openrtb": {"version": 2.6}},
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertEqual([], [f.type for f in found if f.type == "ortb_version_drift"])

    def test_top_level_location_still_satisfies_it(self):
        golden = {"bidder_info": {"ortb_version": "2.6"}}
        found = sfu.compare_fields("b", "go", golden, {"openrtb": {"version": 2.6}},
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertEqual([], [f.type for f in found if f.type == "ortb_version_drift"])

    def test_a_real_divergence_is_still_reported(self):
        """The alternate path must not become a way to pass by recording anything
        anywhere: a value that disagrees still drifts."""
        golden = {"bidder_info": {"ortb_version": None,
                                  "yaml_extra_fields": {"openrtb": {"version": 2.5}}}}
        found = sfu.compare_fields("b", "go", golden, {"openrtb": {"version": 2.6}},
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertIn("ortb_version_drift", [f.type for f in found])

    def test_absent_in_both_locations_still_reports_the_addition(self):
        """thetradedesk's case: upstream added the key after the pin, and the
        golden records it in neither place, so the finding is real."""
        golden = {"bidder_info": {"ortb_version": None,
                                  "yaml_extra_fields": {"openrtb": {"gpp_supported": True}}}}
        found = sfu.compare_fields("b", "go", golden, {"openrtb": {"version": 2.6}},
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertIn("ortb_version_drift", [f.type for f in found])

    def test_alt_paths_are_tried_in_order_and_stop_at_the_first_hit(self):
        spec = sfu.FieldSpec("x", ("a",), ("a",), sfu.SEVERITY_WARN,
                             golden_keys_alt=(("b",), ("c",)))
        found = sfu.compare_fields("b", "go", {"b": 1, "c": 2}, {"a": 1}, (spec,), "w")
        self.assertEqual([], found, "the first alternate should have satisfied it")


class TestGoAliasInheritance(unittest.TestCase):
    """A Go alias yaml carries only what it overrides, so the fields it inherits
    were never compared.

    `compare_fields` skips a field whose upstream key is absent and whose
    FieldSpec declares no `absent_default` -- true of `endpoint` and
    `endpointCompression`. So for `152media.yaml`, which is `aliasOf: adkernel`
    plus `gvlVendorID`, the golden's recorded endpoint could diverge from the
    parent's indefinitely with nothing reported. The Java path has resolved this
    since it was written (`resolve_java_adapter_section`); these are the Go
    counterpart's tests.
    """

    PARENT = "endpoint: \"http://parent/hb?zone={{.ZoneID}}\"\nendpointCompression: \"GZIP\"\ngvlVendorID: 14\n"

    def _resolve(self, alias_yaml: str, golden: dict) -> dict:
        source = make_source({"static/bidder-info/parent.yaml": self.PARENT})
        return sfu.resolve_go_bidder_info(yaml.safe_load(alias_yaml), golden, source)

    def test_inherited_fields_come_from_the_parent(self):
        got = self._resolve("aliasOf: parent\ngvlVendorID: 1111\n",
                            {"meta": {"alias_of": "parent"}})
        self.assertEqual("http://parent/hb?zone={{.ZoneID}}", got["endpoint"])
        self.assertEqual("GZIP", got["endpointCompression"])

    def test_alias_overrides_win_over_the_parent(self):
        got = self._resolve("aliasOf: parent\ngvlVendorID: 1111\n",
                            {"meta": {"alias_of": "parent"}})
        self.assertEqual(1111, got["gvlVendorID"])

    def test_aliasof_is_not_carried_into_the_merged_view(self):
        """`aliasOf` is the alias's own marker, not an inherited field; leaving it
        in would compare against the parent's absent `aliasOf`."""
        got = self._resolve("aliasOf: parent\n", {"meta": {"alias_of": "parent"}})
        self.assertNotIn("aliasOf", got)

    def test_parent_aliases_block_is_not_inherited(self):
        """A parent's `aliases:` map describes its children, not this child."""
        source = make_source({"static/bidder-info/parent.yaml":
                              self.PARENT + "aliases:\n  sibling: ~\n"})
        got = sfu.resolve_go_bidder_info(yaml.safe_load("aliasOf: parent\n"),
                                         {"meta": {"alias_of": "parent"}}, source)
        self.assertNotIn("aliases", got)

    def test_non_alias_doc_is_returned_untouched(self):
        source = make_source({})
        doc = {"endpoint": "http://own/", "endpointCompression": "gzip"}
        self.assertEqual(doc, sfu.resolve_go_bidder_info(doc, {"meta": {}}, source))

    def test_unreadable_parent_degrades_instead_of_raising(self):
        """A parent that cannot be fetched falls back to the alias's own doc --
        the previous behaviour -- rather than failing the whole scan."""
        source = make_source({})
        doc = {"aliasOf": "gone", "gvlVendorID": 7}
        self.assertEqual(doc, sfu.resolve_go_bidder_info(doc, {"meta": {"alias_of": "gone"}}, source))

    def test_inherited_endpoint_drift_is_now_reported(self):
        """End to end: the golden records the endpoint it inherited, the parent's
        endpoint changes, and the finding fires. Before the resolver this
        comparison was skipped because the alias yaml has no `endpoint` key."""
        golden = {"meta": {"alias_of": "parent"},
                  "bidder_info": {"endpoint": "http://old/hb"}}
        effective = self._resolve("aliasOf: parent\n", golden)
        found = sfu.compare_fields("152media", "go", golden, effective,
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertIn("endpoint_drift", [f.type for f in found])

    def test_wiring_end_to_end_through_compare_bidder_go(self):
        """The resolver being CALLED is the load-bearing part. Unit tests that
        invoke it directly stay green when `_compare_info` stops using it, so
        this one drives the whole comparison the way the scan does: an alias
        golden whose recorded endpoint matches its parent's must produce no
        endpoint finding, which is only true if the merge happened."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            golden_path = write_golden(tmp, "152media", {
                "adapter_spec_version": "2.1.0",
                "spec_kind": "prebid-server-adapter",
                "source_language": "go",
                "provenance": {"source": {"resolved_commit": "d" * 40}},
                "meta": {"bidder_name": "152media", "is_alias": True,
                         "alias_of": "adkernel", "disabled": False},
                "bidder_info": {
                    "endpoint": "http://pbs.adksrv.com/hb?zone={{.ZoneID}}",
                    "endpoint_compression": "GZIP",
                    "gvl_vendor_id": 1111,
                    "maintainer": {"email": "x@y.z"},
                },
            })
            upstream = {
                "static/bidder-info/152media.yaml": "aliasOf: adkernel\ngvlVendorID: 1111\n",
                "static/bidder-info/adkernel.yaml": yaml.safe_dump({
                    "endpoint": "http://pbs.adksrv.com/hb?zone={{.ZoneID}}",
                    "endpointCompression": "GZIP",
                    "maintainer": {"email": "x@y.z"},
                    "gvlVendorID": 14,
                    "aliases": {"152media": None},
                }),
            }
            findings = sfu.compare_bidder_go("152media", golden_path, make_source(upstream))
            drift = [f.type for f in findings if f.type.endswith("_drift")]
            self.assertEqual([], drift,
                             f"inherited fields should compare clean once merged; got {findings}")

    def test_wiring_reports_inherited_divergence_end_to_end(self):
        """The other direction: the parent's endpoint moves, the alias yaml still
        declares nothing, and the finding fires."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            golden_path = write_golden(tmp, "152media", {
                "adapter_spec_version": "2.1.0",
                "spec_kind": "prebid-server-adapter",
                "source_language": "go",
                "provenance": {"source": {"resolved_commit": "d" * 40}},
                "meta": {"bidder_name": "152media", "is_alias": True,
                         "alias_of": "adkernel", "disabled": False},
                "bidder_info": {"endpoint": "http://pbs.adksrv.com/hb?zone={{.ZoneID}}",
                                "maintainer": {"email": "x@y.z"}},
            })
            upstream = {
                "static/bidder-info/152media.yaml": "aliasOf: adkernel\n",
                "static/bidder-info/adkernel.yaml": yaml.safe_dump({
                    "endpoint": "http://MOVED.example/hb?zone={{.ZoneID}}",
                    "maintainer": {"email": "x@y.z"},
                }),
            }
            findings = sfu.compare_bidder_go("152media", golden_path, make_source(upstream))
            self.assertIn("endpoint_drift", [f.type for f in findings])

    def test_matching_inherited_endpoint_is_not_drift(self):
        golden = {"meta": {"alias_of": "parent"},
                  "bidder_info": {"endpoint": "http://parent/hb?zone={{.ZoneID}}"}}
        effective = self._resolve("aliasOf: parent\n", golden)
        found = sfu.compare_fields("152media", "go", golden, effective,
                                   sfu.GO_BIDDER_INFO_FIELDS, "bidder_info")
        self.assertNotIn("endpoint_drift", [f.type for f in found])


class TestWorkflowEscalation(unittest.TestCase):
    """Runs the shipped YAML's own shell body against a stubbed `gh`."""

    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load(WORKFLOW_PATH.read_text())
        cls.job = cls.doc["jobs"]["sync"]
        cls.steps = {s.get("name"): s for s in cls.job["steps"] if s.get("name")}

    def _run_step(self, step_name: str, exit_code: str, existing: str):
        step = self.steps[step_name]
        body = _substitute(step["run"], exit_code)
        self.assertNotIn("${{", body, "unsubstituted workflow expression")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bindir = tmp / "bin"
            bindir.mkdir()
            gh = bindir / "gh"
            gh.write_text(GH_STUB)
            gh.chmod(0o755)
            log = tmp / "gh.log"
            log.touch()
            report = tmp / "scripts/output/drift-report.md"
            report.parent.mkdir(parents=True)
            report.write_text("# Drift Report\n\n**Summary**: 10 fail, 24 warn.\n")

            env = dict(os.environ)
            for k, v in (self.doc.get("env") or {}).items():
                env[k] = str(v)
            for k, v in (step.get("env") or {}).items():
                env[k] = _substitute(str(v), exit_code)
            env.update({
                "PATH": f"{bindir}{os.pathsep}{env['PATH']}",
                "GH_LOG": str(log),
                "STUB_EXISTING": existing,
                "GITHUB_REPOSITORY": "prebid/prebid-agent-skills",
                "GITHUB_RUN_ID": "99",
            })
            script = tmp / "step.sh"
            script.write_text(body)
            proc = subprocess.run(["bash", str(script)], cwd=tmp, env=env,
                                  capture_output=True, text=True)
            calls = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
            body_md = (tmp / "body.md").read_text() if (tmp / "body.md").exists() else None
            return proc, calls, body_md

    @staticmethod
    def _verbs(calls):
        return [c[1] for c in calls if c[:1] == ["issue"]]

    def test_job_has_the_minimum_permission_to_escalate(self):
        self.assertEqual("write", self.job["permissions"]["issues"])
        self.assertEqual("read", self.job["permissions"]["contents"])

    def test_job_grants_no_other_write_scopes(self):
        writes = {k for k, v in self.job["permissions"].items() if v == "write"}
        self.assertEqual({"issues"}, writes)

    def test_drift_with_no_existing_issue_files_exactly_one(self):
        proc, calls, body = self._run_step(
            "File or update the drift tracking issue", "1", "none")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(["create"], self._verbs(calls))
        self.assertIn("Drift Report", body)

    def test_drift_with_an_open_issue_updates_it_instead_of_opening_another(self):
        proc, calls, _ = self._run_step(
            "File or update the drift tracking issue", "1", "open")
        self.assertEqual(0, proc.returncode, proc.stderr)
        verbs = self._verbs(calls)
        self.assertNotIn("create", verbs)
        self.assertIn("edit", verbs)

    def test_drift_with_a_closed_issue_reopens_it(self):
        proc, calls, _ = self._run_step(
            "File or update the drift tracking issue", "1", "closed")
        self.assertEqual(0, proc.returncode, proc.stderr)
        verbs = self._verbs(calls)
        self.assertNotIn("create", verbs)
        self.assertIn("reopen", verbs)

    def test_clean_run_closes_the_open_issue(self):
        proc, calls, _ = self._run_step(
            "File or update the drift tracking issue", "0", "open")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(["comment", "close"], self._verbs(calls))

    def test_clean_run_with_no_issue_does_nothing(self):
        proc, calls, _ = self._run_step(
            "File or update the drift tracking issue", "0", "none")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual([], self._verbs(calls))

    def test_instrument_failure_says_it_could_not_scan(self):
        proc, calls, body = self._run_step(
            "File or update the drift tracking issue", "3", "none")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(["create"], self._verbs(calls))
        self.assertIn("could not scan", body)

    def test_exit_code_enforcement(self):
        """The sync exit alone, with the other steps clean.

        Exit 1 no longer fails the job on its own. The scan compares pinned
        goldens against current master, so exit 1 means "findings exist", which
        is its resting state; whether those findings are known is the
        accepted-drift step's verdict, checked separately below. Exit 3 still
        fails: a zero-input scan is an instrument failure, not a verdict.
        """
        step = self.steps["Enforce sync exit code"]
        for sync_exit, expected in (("0", 0), ("1", 0), ("2", 0), ("3", 1), ("7", 1)):
            body = _substitute(step["run"], sync_exit)
            self.assertNotIn("${{", body)
            proc = subprocess.run(["bash", "-c", body], capture_output=True, text=True)
            self.assertEqual(expected, proc.returncode,
                             f"sync exit {sync_exit}: {proc.stdout}{proc.stderr}")

    def test_claims_or_refs_failing_fails_the_job(self):
        """Both non-blocking steps must reach the exit code.

        They are `continue-on-error` so a failure there cannot mask the drift
        report — which means the only thing that turns them into a verdict is
        this step reading their outputs. If it did not, a claim that stopped
        holding upstream, or a params ref that stopped matching it, would be
        reported into a log nobody reads and the job would go green.
        """
        step = self.steps["Enforce sync exit code"]
        cases = [
            ("0", "0", "0", "0", 0, "all clean"),
            ("0", "1", "0", "0", 1, "a registered claim no longer holds"),
            ("0", "0", "1", "0", 1, "a params ref no longer matches upstream"),
            ("2", "1", "1", "0", 1, "warn-only sync does not excuse the others"),
            ("0", "1", "1", "0", 1, "both"),
            ("1", "0", "0", "1", 1, "drift that is not in the accepted-drift baseline"),
            ("1", "0", "0", "0", 0, "drift that IS in the baseline is not a failure"),
            ("1", "0", "0", "", 1, "the baseline step never reached its echo"),
        ]
        for sync, claims, refs, baseline, expected, why in cases:
            body = _substitute(step["run"], sync, claims, refs, baseline)
            self.assertNotIn("${{", body)
            proc = subprocess.run(["bash", "-c", body], capture_output=True, text=True)
            self.assertEqual(expected, proc.returncode,
                             f"{why}: {proc.stdout}{proc.stderr}")

    def test_fixture_digest_verdict_reaches_the_exit_code(self):
        """The fixture-digest step is `continue-on-error`, so the only thing that
        turns it into a verdict is this step reading its output. A digest that
        stopped describing its file, or a coverage regression, would otherwise be
        reported into a log nobody reads."""
        step = self.steps["Enforce sync exit code"]
        cases = [
            ("0", 0, "clean"),
            ("1", 1, "a digest no longer describes its file, or coverage regressed"),
            ("", 1, "the step never reached its echo"),
        ]
        for fixtures, expected, why in cases:
            body = _substitute(step["run"], "0", "0", "0", "0", fixtures)
            self.assertNotIn("${{", body)
            proc = subprocess.run(["bash", "-c", body], capture_output=True, text=True)
            self.assertEqual(expected, proc.returncode,
                             f"{why} (fixtures={fixtures!r}): {proc.stdout}{proc.stderr}")

    def test_a_step_that_never_ran_is_not_a_pass(self):
        """An empty step output means the step died before its echo.

        This is the failure this job exists to catch, turned on the job itself:
        zero checks run is not zero problems found. GitHub renders an unset
        output as the empty string, so `[ "$CLAIMS" != "0" ]` alone would have
        read it as... not-zero, and failed — but only by accident of string
        comparison, and with a message blaming a claim instead of the step. The
        emptiness is checked explicitly so the error says which step did not
        finish.
        """
        step = self.steps["Enforce sync exit code"]
        for claims, refs, needle in (("", "0", "upstream-claims step produced no exit code"),
                                     ("0", "", "R2c params-ref step produced no exit code")):
            body = _substitute(step["run"], "0", claims, refs)
            proc = subprocess.run(["bash", "-c", body], capture_output=True, text=True)
            self.assertEqual(1, proc.returncode, f"{proc.stdout}{proc.stderr}")
            self.assertIn(needle, proc.stdout + proc.stderr)

    def test_r2c_step_is_present_and_non_blocking(self):
        """R2c must run in this job and must not short-circuit the drift report."""
        step = self.steps["Verify bidder-params refs against upstream (R2c)"]
        self.assertTrue(step.get("continue-on-error"),
                        "R2c must not mask the drift report; the verdict comes from "
                        "the enforcement step")
        self.assertEqual("refs", step.get("id"),
                         "the enforcement step reads steps.refs.outputs.exit")
        self.assertIn("scripts/verify-params-refs.py", step["run"])
        self.assertIn("--go-checkout .upstream/go", step["run"])
        self.assertIn("--java-checkout .upstream/java", step["run"])
        self.assertNotIn("--allow-unverifiable", step["run"],
                         "an unverifiable ref is not a verified one; do not blanket-allow it")

    def test_sync_step_does_not_short_circuit_the_escalation(self):
        # The escalation must run even when the sync step reports drift.
        self.assertEqual(
            "always()",
            self.steps["File or update the drift tracking issue"]["if"].strip())


if __name__ == "__main__":
    unittest.main()
