#!/usr/bin/env python3
"""Phase D Tests-H2: fixture-driven end-to-end render tests.

The per-template tests in test_port_go2java_templates.py and
test_port_java2go_templates.py prove that templates render given a
hand-crafted ``ctx`` dict; they do NOT prove that the SKILL → context →
template path is consistent end-to-end. This file closes that gap by:

1. Loading a real golden spec from `read/test-fixtures/`.
2. Applying a SKILL-Step-4 spec→context mapping (the simplest fields;
   complex per-rule transformations stay out of scope here).
3. Rendering the simplest target template against the derived context.
4. Asserting that key spec values appear verbatim in the rendered output.

If the SKILL's actual context-assembly diverges from these mappings, the
operator-side mvn / go-build run catches the divergence; these tests
catch the simpler "the template's required ctx keys differ from what
the spec carries" mismatch BEFORE the operator runs.

Run from repo root:
    python3 -m pytest scripts/tests/test_port_e2e_fixtures.py
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, Dict

import yaml

try:
    import jinja2
except ImportError:  # pragma: no cover
    jinja2 = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[2]
GO_FIXTURES = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
JAVA_FIXTURES = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"
PORT_GO2JAVA_TEMPLATES = REPO_ROOT / "prebid-server-java" / "port-go2java" / "templates"
PORT_JAVA2GO_TEMPLATES = REPO_ROOT / "prebid-server-go" / "port-java2go" / "templates"

GO_MODULE_VERSION = "v4"


def _render(templates_dir: Path, template_name: str, ctx: Dict[str, Any]) -> str:
    if jinja2 is None:
        raise unittest.SkipTest("jinja2 not installed")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(template_name).render(ctx=ctx)


def _load_golden(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Spec → template-context mappers (mirror SKILL Step 4 work)
# ---------------------------------------------------------------------------


def go_spec_to_java_bidder_config_ctx(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Produce the bidder-config.yaml.j2 ctx from a Go-source golden.

    Mirrors the simplest path through port-go2java SKILL Step 4 — copies
    R5-strict-shared bidder_info fields verbatim, applies the lowercase
    Rule 46 normalization on the bidder name. Rule 33 alias-graph
    inversion / Rule 35 typed-config / Rule 42 IAB cats are out of scope
    here (those would each merit their own e2e test).
    """
    bi = spec.get("bidder_info") or {}
    capabilities = bi.get("capabilities") or {}
    site = capabilities.get("site") or {}
    app = capabilities.get("app") or {}
    dooh = capabilities.get("dooh") or {}
    return {
        "bidder_name": (spec.get("meta") or {}).get("bidder_name", "").lower(),
        "endpoint": bi.get("endpoint") or "",
        "maintainer_email": (bi.get("maintainer") or {}).get("email", ""),
        "gvl_vendor_id": bi.get("gvl_vendor_id"),
        "endpoint_compression": bi.get("endpoint_compression"),
        "modifying_vast_xml": bool(bi.get("modifying_vast_xml_allowed")),
        "geoscope": list(bi.get("geoscope") or []),
        "site_media_types": list(site.get("mediaTypes") or []) or None,
        "app_media_types": list(app.get("mediaTypes") or []) or None,
        "dooh_media_types": list(dooh.get("mediaTypes") or []) or None,
        "aliases": {},
        "user_sync": bi.get("user_sync") or None,
        "ortb_version": bi.get("ortb_version"),
    }


def java_spec_to_go_bidder_info_ctx(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Produce the bidder-info.yaml.j2 (Go target) ctx from a Java-source golden."""
    bi = spec.get("bidder_info") or {}
    capabilities = bi.get("capabilities") or {}
    site = capabilities.get("site") or {}
    app = capabilities.get("app") or {}
    dooh = capabilities.get("dooh") or {}
    return {
        "endpoint": bi.get("endpoint") or "",
        "maintainer_email": (bi.get("maintainer") or {}).get("email", ""),
        "gvl_vendor_id": bi.get("gvl_vendor_id"),
        "endpoint_compression": bi.get("endpoint_compression"),
        "modifying_vast_xml": bool(bi.get("modifying_vast_xml_allowed")),
        "geoscope": list(bi.get("geoscope") or []),
        "site_media_types": list(site.get("mediaTypes") or []) or None,
        "app_media_types": list(app.get("mediaTypes") or []) or None,
        "dooh_media_types": list(dooh.get("mediaTypes") or []) or None,
        "alias_of": (spec.get("meta") or {}).get("alias_of"),
        "user_sync": bi.get("user_sync") or None,
    }


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


class TestKoblerGoToJava(unittest.TestCase):
    """End-to-end: kobler Go-source golden → port-go2java bidder-config emission.

    Validates that the Go-source spec's bidder_info fields propagate
    through the spec→ctx mapper and out the Jinja template into a
    well-formed Java bidder-config YAML.
    """

    def setUp(self):
        self.spec = _load_golden(GO_FIXTURES / "kobler.golden.spec.yaml")
        self.ctx = go_spec_to_java_bidder_config_ctx(self.spec)
        self.rendered = _render(
            PORT_GO2JAVA_TEMPLATES, "bidder-config.yaml.j2", self.ctx,
        )
        self.parsed = yaml.safe_load(self.rendered)

    def test_endpoint_from_spec_propagates(self):
        # Source-of-truth: prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml
        # bidder_info.endpoint
        spec_endpoint = self.spec["bidder_info"]["endpoint"]
        self.assertEqual(self.parsed["adapters"]["kobler"]["endpoint"], spec_endpoint)

    def test_maintainer_email_propagates(self):
        spec_email = self.spec["bidder_info"]["maintainer"]["email"]
        self.assertEqual(
            self.parsed["adapters"]["kobler"]["meta-info"]["maintainer-email"],
            spec_email,
        )

    def test_geoscope_propagates(self):
        spec_geo = self.spec["bidder_info"]["geoscope"]
        self.assertEqual(
            self.parsed["adapters"]["kobler"]["geoscope"], list(spec_geo),
        )

    def test_gvl_vendor_id_propagates(self):
        # kobler has gvl_vendor_id = 0 in the golden; emission should preserve
        # zero (NOT omit it as falsy).
        spec_gvl = self.spec["bidder_info"]["gvl_vendor_id"]
        self.assertEqual(self.parsed["adapters"]["kobler"]["meta-info"]["vendor-id"], spec_gvl)

    def test_endpoint_compression_propagates_camel_to_kebab(self):
        # Go-side YAML carries camelCase endpointCompression; Java target
        # emits kebab-case endpoint-compression. The bidder-info golden
        # decodes the camelCase form into the spec's endpoint_compression
        # field; the template renders kebab-case.
        spec_compression = self.spec["bidder_info"]["endpoint_compression"]
        self.assertEqual(
            self.parsed["adapters"]["kobler"]["endpoint-compression"], spec_compression,
        )

    def test_capabilities_media_types_propagate(self):
        spec_site = self.spec["bidder_info"]["capabilities"]["site"]["mediaTypes"]
        spec_app = self.spec["bidder_info"]["capabilities"]["app"]["mediaTypes"]
        meta = self.parsed["adapters"]["kobler"]["meta-info"]
        self.assertEqual(meta["site-media-types"], list(spec_site))
        self.assertEqual(meta["app-media-types"], list(spec_app))


class TestKoblerJavaToGo(unittest.TestCase):
    """End-to-end: kobler Java-source golden → port-java2go bidder-info emission."""

    def setUp(self):
        self.spec = _load_golden(JAVA_FIXTURES / "kobler.golden.spec.yaml")
        self.ctx = java_spec_to_go_bidder_info_ctx(self.spec)
        self.rendered = _render(
            PORT_JAVA2GO_TEMPLATES, "bidder-info.yaml.j2", self.ctx,
        )
        self.parsed = yaml.safe_load(self.rendered)

    def test_endpoint_from_spec_propagates(self):
        spec_endpoint = self.spec["bidder_info"]["endpoint"]
        self.assertEqual(self.parsed["endpoint"], spec_endpoint)

    def test_maintainer_email_propagates(self):
        spec_email = self.spec["bidder_info"]["maintainer"]["email"]
        self.assertEqual(self.parsed["maintainer"]["email"], spec_email)

    def test_geoscope_propagates(self):
        spec_geo = self.spec["bidder_info"]["geoscope"]
        self.assertEqual(self.parsed["geoscope"], list(spec_geo))

    def test_camel_case_yaml_keys_in_go_emission(self):
        """Java-side spec uses kebab-case-equivalent fields (already
        normalized to snake_case in the spec representation); Go-target
        emission uses camelCase YAML keys."""
        if "endpoint_compression" in self.spec["bidder_info"] and self.spec["bidder_info"]["endpoint_compression"]:
            self.assertIn("endpointCompression", self.rendered)
        # The kebab form (Java side) must NOT appear in Go output.
        self.assertNotIn("endpoint-compression", self.rendered)
        self.assertNotIn("vendor-id", self.rendered)


class TestKoblerGoBidderTemplateUsesV4(unittest.TestCase):
    """End-to-end: kobler Java-source golden → port-java2go bidder.go.j2 →
    rendered Go file uses the v4 module path. Catches the D3-B1
    regression class — if a future change defaults module_version
    elsewhere, this test surfaces it without operator validation.
    """

    def test_emitted_imports_use_v4(self):
        spec = _load_golden(JAVA_FIXTURES / "kobler.golden.spec.yaml")
        # Build a minimum-viable bidder.go.j2 ctx from the spec.
        ctx = {
            "package_name": (spec.get("meta") or {}).get("bidder_name", "").lower(),
            "bidder_class_root": "Kobler",
            "uses_currency_conversion": True,
            "imp_ext_class_root": "Kobler",
            "imp_ext_unmarshal_kind": "standard-two-phase",
            "batching_kind": "single-batched",
            "batching_max_imps": None,
            "endpoint_resolution_kind": "static",
            "http_status_kind": "canonical-helpers",
            "bid_type_resolution": "imp-mediatype-introspection",
            "has_extra_info": False,
            "module_version": GO_MODULE_VERSION,
            "imports_extra": [],
            "javadoc_summary": None,
        }
        rendered = _render(PORT_JAVA2GO_TEMPLATES, "bidder.go.j2", ctx)
        self.assertIn(f'"github.com/prebid/prebid-server/{GO_MODULE_VERSION}/adapters"', rendered)
        self.assertNotIn('/v3/', rendered)
        self.assertIn("ImpIDs:  openrtb_ext.GetImpIDs(request.Imp)", rendered)


class TestModuleVersionTableSync(unittest.TestCase):
    """Phase D3-B1 follow-up: the module_version constant in this test
    suite is pinned to the same value as bidder-constant-table.yaml's
    upstream_source.module_version. If upstream bumps to v5 and the
    table refresh runs, this test fires until the test constant updates
    accordingly — surfaces the multi-source pin drift.
    """

    def test_test_constant_matches_table_pin(self):
        table_path = (
            REPO_ROOT
            / "prebid-server-go" / "read" / "skills" / "shared"
            / "bidder-constant-table.yaml"
        )
        with open(table_path, "r", encoding="utf-8") as fh:
            table = yaml.safe_load(fh)
        table_pin = table["upstream_source"]["module_version"]
        self.assertEqual(
            GO_MODULE_VERSION, table_pin,
            f"GO_MODULE_VERSION constant ({GO_MODULE_VERSION!r}) drifted from "
            f"bidder-constant-table.yaml::upstream_source.module_version "
            f"({table_pin!r}); update one of the two."
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
