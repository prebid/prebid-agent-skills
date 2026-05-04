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


def _kobler_ext_imp_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for ext-imp-pojo.java.j2.
    Source spec field: imp.ext.bidder.test (boolean), only field on ExtImpKobler.
    """
    return {
        "bidder_name": "kobler",
        "bidder_class_root": "Kobler",
        "fields": [
            {
                "java_name": "test",
                "json_property": "test",
                "java_type": "Boolean",
                "omit_when_null": False,
                "notes": None,
            },
        ],
        "has_builder": False,
        "imports_extra": [],
        "javadoc_summary": None,
    }


def _kobler_configuration_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for configuration.java.j2.
    Source spec: currency_conversion.used = true; no typed config subclass
    (Rule 35 not fired); no extra constructor args.
    """
    return {
        "bidder_name": "kobler",
        "bidder_class_root": "Kobler",
        "uses_currency_conversion": True,
        "has_typed_config_props": False,
        "typed_config_class_name": None,
        "extra_constructor_args": None,
        "bidder_creator_extra_args": None,
        "user_sync": {},
        "javadoc_summary": None,
    }


class TestExtImpPojoJ2(unittest.TestCase):
    """Tests for templates/ext-imp-pojo.java.j2."""

    def test_renders_kobler_well_formed_class(self):
        rendered = _render("ext-imp-pojo.java.j2", _kobler_ext_imp_ctx())
        self.assertIn("package org.prebid.server.proto.openrtb.ext.request.kobler;", rendered)
        self.assertIn("public class ExtImpKobler {", rendered)
        self.assertIn('@JsonProperty("test")', rendered)
        self.assertIn("Boolean test;", rendered)

    def test_default_lombok_minimal(self):
        rendered = _render("ext-imp-pojo.java.j2", _kobler_ext_imp_ctx())
        # @Value is the canonical minimal Lombok annotation set.
        self.assertIn('@Value(staticConstructor = "of")', rendered)
        # @Builder NOT present in default form.
        self.assertNotIn("@Builder", rendered)

    def test_builder_annotation_when_requested(self):
        ctx = _kobler_ext_imp_ctx()
        ctx["has_builder"] = True
        rendered = _render("ext-imp-pojo.java.j2", ctx)
        self.assertIn("@Builder(toBuilder = true)", rendered)
        self.assertIn("@AllArgsConstructor", rendered)

    def test_jsoninclude_imported_when_omit_when_null(self):
        ctx = _kobler_ext_imp_ctx()
        ctx["fields"][0]["omit_when_null"] = True
        rendered = _render("ext-imp-pojo.java.j2", ctx)
        self.assertIn("import com.fasterxml.jackson.annotation.JsonInclude;", rendered)
        self.assertIn("@JsonInclude(JsonInclude.Include.NON_NULL)", rendered)

    def test_no_jsoninclude_when_default(self):
        rendered = _render("ext-imp-pojo.java.j2", _kobler_ext_imp_ctx())
        self.assertNotIn("import com.fasterxml.jackson.annotation.JsonInclude;", rendered)
        self.assertNotIn("@JsonInclude", rendered)

    def test_multi_field_pojo_with_blank_separator(self):
        """Multiple fields are separated by exactly one blank line per
        EmptyLineSeparator checkstyle rule (java-artifact-shapes.md §5)."""
        ctx = _kobler_ext_imp_ctx()
        ctx["fields"] = [
            {"java_name": "test", "json_property": "test", "java_type": "Boolean",
             "omit_when_null": False, "notes": None},
            {"java_name": "placementId", "json_property": "placementId", "java_type": "String",
             "omit_when_null": False, "notes": None},
        ]
        rendered = _render("ext-imp-pojo.java.j2", ctx)
        # Both fields present.
        self.assertIn("Boolean test;", rendered)
        self.assertIn("String placementId;", rendered)

    def test_field_notes_emit_as_comment(self):
        ctx = _kobler_ext_imp_ctx()
        ctx["fields"][0]["notes"] = "Whether the request is for testing only."
        rendered = _render("ext-imp-pojo.java.j2", ctx)
        self.assertIn("// Whether the request is for testing only.", rendered)


class TestConfigurationJ2(unittest.TestCase):
    """Tests for templates/configuration.java.j2."""

    def test_renders_kobler_well_formed_class(self):
        rendered = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertIn("package org.prebid.server.spring.config.bidder;", rendered)
        self.assertIn("public class KoblerConfiguration {", rendered)
        self.assertIn('private static final String BIDDER_NAME = "kobler";', rendered)
        self.assertIn("BidderDeps koblerBidderDeps(", rendered)

    def test_currency_conversion_injection_present(self):
        rendered = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertIn("import org.prebid.server.currency.CurrencyConversionService;", rendered)
        self.assertIn("CurrencyConversionService currencyConversionService", rendered)
        self.assertIn(
            "new KoblerBidder(config.getEndpoint(), currencyConversionService, mapper)",
            rendered,
        )

    def test_currency_conversion_omitted_when_unused(self):
        ctx = _kobler_configuration_ctx()
        ctx["uses_currency_conversion"] = False
        rendered = _render("configuration.java.j2", ctx)
        self.assertNotIn("CurrencyConversionService", rendered)
        # Bean lambda still has mapper but no currency arg.
        self.assertIn("new KoblerBidder(config.getEndpoint(), mapper)", rendered)

    def test_typed_config_props_uses_subclass(self):
        ctx = _kobler_configuration_ctx()
        ctx["has_typed_config_props"] = True
        ctx["typed_config_class_name"] = "KoblerBidderConfigurationProperties"
        rendered = _render("configuration.java.j2", ctx)
        self.assertIn("KoblerBidderConfigurationProperties configurationProperties()", rendered)
        self.assertIn("return new KoblerBidderConfigurationProperties();", rendered)
        self.assertIn(
            "KoblerBidderConfigurationProperties koblerConfigurationProperties,",
            rendered,
        )

    def test_property_source_matches_bidder_config_path(self):
        rendered = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertIn(
            'classpath:/bidder-config/kobler.yaml',
            rendered,
        )

    def test_typed_config_props_drops_bidderconfigurationproperties_import(self):
        """When the typed subclass replaces the generic
        BidderConfigurationProperties, the latter import would be unused —
        checkstyle UnusedImports rule would flag it. Template must drop it."""
        ctx = _kobler_configuration_ctx()
        ctx["has_typed_config_props"] = True
        ctx["typed_config_class_name"] = "KoblerBidderConfigurationProperties"
        rendered = _render("configuration.java.j2", ctx)
        self.assertNotIn(
            "import org.prebid.server.spring.config.bidder.model.BidderConfigurationProperties;",
            rendered,
        )

    def test_validated_only_when_typed_config_props(self):
        """@Validated annotation appears only with typed config subclass
        (Bean Validation activation); standard form omits it AND its import."""
        std = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertNotIn("@Validated", std)
        self.assertNotIn("import org.springframework.validation.annotation.Validated;", std)
        ctx = _kobler_configuration_ctx()
        ctx["has_typed_config_props"] = True
        ctx["typed_config_class_name"] = "X"
        typed = _render("configuration.java.j2", ctx)
        self.assertIn("@Validated", typed)
        self.assertIn("import org.springframework.validation.annotation.Validated;", typed)


class TestRequiredArtifacts(unittest.TestCase):
    """Sanity: every Java template referenced by SKILL.md Step 5 either exists
    or is flagged in the templates STUB.md as a future deliverable."""

    EXPECTED_TEMPLATES = (
        "bidder-config.yaml.j2",            # D2.1 commit
        "ext-imp-pojo.java.j2",             # D2.2 commit
        "configuration.java.j2",            # D2.2 commit
        # Future D2 commits author:
        # "bidder.java.j2",
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
