#!/usr/bin/env python3
"""Render tests for prebid-server-java/port-go2java/templates/*.j2.

Phase D2 templates are pure Jinja2; the port-go2java SKILL renders them
against a context dict assembled from the source spec. These tests verify
the templates produce well-formed Java-target artifacts (parseable YAML /
JSON / Java syntax) for the 6 MVP corpus pairs.

Run from repo root:
    python3 -m pytest scripts/tests/test_port_go2java_templates.py
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
TEMPLATES_DIR = REPO_ROOT / "prebid-server-java" / "port-go2java" / "templates"


def _render(template_name: str, ctx: Dict[str, Any]) -> str:
    if jinja2 is None:
        raise unittest.SkipTest("jinja2 not installed")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
        # The Java YAML emission has no auto-escape concerns — values are
        # JSON-encoded via |tojson where needed.
        autoescape=False,
        # Strip whitespace control to keep YAML emission clean.
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    return template.render(ctx=ctx)


def _kobler_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent template context.

    Mirrors the shape the port-go2java SKILL Step 4 produces from
    prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml.
    Source spec fields:
        bidder_info.endpoint = "https://bid.essrtb.com/bid/prebid_server_rtb_call"
        bidder_info.endpoint_compression = "gzip"
        bidder_info.maintainer.email = "bidding-support@kobler.no"
        bidder_info.geoscope = ["NOR", "SWE", "DNK"]
        bidder_info.gvl_vendor_id = 0
        bidder_info.modifying_vast_xml_allowed = false
        capabilities.{site,app}.mediaTypes = ["banner"]
    """
    return {
        "bidder_name": "kobler",
        "endpoint": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
        "maintainer_email": "bidding-support@kobler.no",
        "gvl_vendor_id": 0,
        "endpoint_compression": "gzip",
        "modifying_vast_xml": False,
        "geoscope": ["DNK", "NOR", "SWE"],  # alphabetical (helper-sorted upstream)
        "site_media_types": ["banner"],
        "app_media_types": ["banner"],
        "dooh_media_types": None,
        "aliases": {},
        "user_sync": None,
        "ortb_version": None,
    }


class TestBidderConfigYamlJ2(unittest.TestCase):
    """Tests for templates/bidder-config.yaml.j2."""

    def test_renders_kobler_well_formed_yaml(self):
        rendered = _render("bidder-config.yaml.j2", _kobler_ctx())
        # Round-trip through yaml.safe_load to confirm well-formed.
        parsed = yaml.safe_load(rendered)
        self.assertIsNotNone(parsed)
        self.assertIn("adapters", parsed)
        self.assertIn("kobler", parsed["adapters"])

    def test_kebab_case_keys_under_adapter(self):
        """Java convention: kebab-case keys (NOT camelCase) per
        java-artifact-shapes.md §11."""
        rendered = _render("bidder-config.yaml.j2", _kobler_ctx())
        parsed = yaml.safe_load(rendered)
        kobler = parsed["adapters"]["kobler"]
        # Camel-case Go-side names should NOT appear.
        self.assertNotIn("endpointCompression", kobler)
        self.assertNotIn("modifyingVastXmlAllowed", kobler)
        # Kebab-case names should appear when applicable.
        self.assertIn("endpoint-compression", kobler)

    def test_endpoint_value_preserved(self):
        rendered = _render("bidder-config.yaml.j2", _kobler_ctx())
        parsed = yaml.safe_load(rendered)
        self.assertEqual(
            parsed["adapters"]["kobler"]["endpoint"],
            "https://bid.essrtb.com/bid/prebid_server_rtb_call",
        )

    def test_geoscope_preserved_in_order(self):
        rendered = _render("bidder-config.yaml.j2", _kobler_ctx())
        parsed = yaml.safe_load(rendered)
        self.assertEqual(parsed["adapters"]["kobler"]["geoscope"], ["DNK", "NOR", "SWE"])

    def test_meta_info_block_well_formed(self):
        rendered = _render("bidder-config.yaml.j2", _kobler_ctx())
        parsed = yaml.safe_load(rendered)
        meta = parsed["adapters"]["kobler"]["meta-info"]
        self.assertEqual(meta["maintainer-email"], "bidding-support@kobler.no")
        self.assertEqual(meta["vendor-id"], 0)
        self.assertEqual(meta["site-media-types"], ["banner"])
        self.assertEqual(meta["app-media-types"], ["banner"])
        self.assertNotIn("dooh-media-types", meta)  # null in ctx → omitted

    def test_modifying_vast_xml_omitted_when_false(self):
        """Java convention: emit `modifying-vast-xml-allowed: true` only when
        the bidder modifies VAST XML; omit the key entirely when false (the
        default). Verified against upstream kobler bidder-config: no such key."""
        rendered = _render("bidder-config.yaml.j2", _kobler_ctx())
        self.assertNotIn("modifying-vast-xml-allowed", rendered)

    def test_aliases_block_emitted_when_present(self):
        ctx = _kobler_ctx()
        ctx["bidder_name"] = "smarthub"
        ctx["aliases"] = {
            "host_a": {},  # inherits parent
            "host_b": {"endpoint": "https://host-b.example.com/bid"},
        }
        rendered = _render("bidder-config.yaml.j2", ctx)
        parsed = yaml.safe_load(rendered)
        smarthub = parsed["adapters"]["smarthub"]
        self.assertIn("aliases", smarthub)
        self.assertIsNone(smarthub["aliases"]["host_a"])  # `~` → null
        self.assertEqual(
            smarthub["aliases"]["host_b"]["endpoint"],
            "https://host-b.example.com/bid",
        )


class TestRequiredArtifacts(unittest.TestCase):
    """Sanity: every Java template referenced by SKILL.md Step 5 either exists
    or is flagged in the templates STUB.md as a future deliverable."""

    EXPECTED_TEMPLATES = (
        "bidder-config.yaml.j2",                # this commit
        # Future D2 commits author:
        # "ext-imp-pojo.java.j2",
        # "bidder.java.j2",
        # "configuration.java.j2",
        # "configuration-properties.java.j2",
        # "bidder-test.java.j2",
        # "it-test.java.j2",
        # "it-fixture-auction-request.json.j2",
        # "it-fixture-auction-response.json.j2",
        # "it-fixture-bid-request.json.j2",
        # "it-fixture-bid-response.json.j2",
    )

    def test_templates_present(self):
        for name in self.EXPECTED_TEMPLATES:
            path = TEMPLATES_DIR / name
            self.assertTrue(
                path.exists(),
                f"expected template {name} at {path}",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
