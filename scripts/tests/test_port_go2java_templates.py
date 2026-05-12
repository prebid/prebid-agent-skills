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

import json
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


def _kobler_bidder_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for bidder.java.j2.

    Matches kobler's golden spec shape:
        batching = single-batched
        endpoint_resolution = dev-prod-toggle (handled inline per Rule 13)
        imp_ext_unmarshal = standard-two-phase
        http_status = canonical-helpers (Rule 30)
        currency_conversion = used = true
        bid_type = imp-mediatype-introspection
    """
    return {
        "bidder_name": "kobler",
        "bidder_class_root": "Kobler",
        "uses_currency_conversion": True,
        "imp_ext_class_root": "Kobler",
        "imp_ext_unmarshal_kind": "standard-two-phase",
        "batching_kind": "single-batched",
        "batching_max_imps": None,
        "endpoint_resolution_kind": "dev-prod-toggle",
        "headers_collapse": False,
        "http_status_kind": "canonical-helpers",
        "bid_type_resolution": "imp-mediatype-introspection",
        "javadoc_summary": None,
        "imports_extra": [],
    }


def _kobler_bidder_test_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for bidder-test.java.j2."""
    return {
        "bidder_name": "kobler",
        "bidder_class_root": "Kobler",
        "imp_ext_class_root": "Kobler",
        "uses_currency_conversion": True,
        "has_typed_config_props": False,
        "endpoint_url_for_test": "https://test.endpoint.com/",
        "imp_ext_field_pairs": [
            {"java_name": "test", "default_value": "true"},
        ],
        "scenario_methods": [
            {
                "method_name": "makeHttpRequestsShouldUseDevEndpointWhenTestFlagIsSet",
                "summary": "kobler dev-prod-toggle test scenario",
            },
        ],
        "javadoc_summary": None,
    }


def _kobler_it_test_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for it-test.java.j2."""
    return {
        "bidder_name": "kobler",
        "bidder_class_root": "Kobler",
        "endpoint_path": "/kobler-exchange",
        "scenarios": [
            {
                "method_name": "openrtb2AuctionShouldRespondWithBidsFromKoblerBidder",
                "summary": "Happy path: kobler returns a single banner bid for one imp.",
                "bid_request_path": "openrtb2/kobler/test-kobler-bid-request.json",
                "bid_response_path": "openrtb2/kobler/test-kobler-bid-response.json",
                "auction_request_path": "openrtb2/kobler/test-auction-kobler-request.json",
                "auction_response_path": "openrtb2/kobler/test-auction-kobler-response.json",
                "expected_seats": ["kobler"],
            },
        ],
        "javadoc_summary": None,
    }


def _kobler_auction_request_ctx() -> Dict[str, Any]:
    return {
        "request_id": "kobler-banner-1",
        "imps": [
            {
                "id": "imp-1",
                "mediatype": "banner",
                "mediatype_props": {"format": [{"w": 300, "h": 250}]},
                "ext_bidder": {"test": True},
            },
        ],
        "bidder_name": "kobler",
        "tmax": 5000,
        "cur": ["USD"],
        "site_page": "https://example.com/page",
        "app_bundle": None,
        "publisher_id": "pub-1",
    }


def _kobler_bid_response_ctx() -> Dict[str, Any]:
    return {
        "response_id": "kobler-resp-1",
        "cur": "USD",
        "bidder_name": "kobler",
        "bids": [
            {
                "id": "bid-1",
                "impid": "imp-1",
                "price": "1.50",
                "adm": "<creative/>",
                "crid": "creative-1",
                "adomain": ["advertiser.example.com"],
                "cat": None,
                "w": 300,
                "h": 250,
                "ext": None,
            },
        ],
    }


def _kobler_auction_response_ctx() -> Dict[str, Any]:
    return {
        "response_id": "kobler-resp-1",
        "cur": "USD",
        "bidder_name": "kobler",
        "bids": [
            {
                "id": "bid-1",
                "impid": "imp-1",
                "price": "1.50",
                "adm": "<creative/>",
                "crid": "creative-1",
                "adomain": ["advertiser.example.com"],
                "cat": None,
                "w": 300,
                "h": 250,
                "ext_prebid_type": "banner",
                "ext_origbidcpm": "1.50",
                "ext_origbidcur": "USD",
            },
        ],
    }


def _adverxo_typed_config_ctx() -> Dict[str, Any]:
    """Synthetic adverxo-equivalent context for configuration-properties.java.j2.
    Adverxo (Rule 35 master sample) has a typed config subclass with
    bidder-specific fields beyond the standard endpoint/enabled/usersync set.
    """
    return {
        "bidder_class_root": "Adverxo",
        "typed_fields": [
            {
                "java_name": "auctionEndpoint",
                "java_type": "String",
                "validation_annotations": ["@NotBlank"],
                "notes": "Endpoint for the auction call; differs from the registration endpoint.",
                "default_value": None,
            },
            {
                "java_name": "registrationEndpoint",
                "java_type": "String",
                "validation_annotations": ["@NotBlank"],
                "notes": None,
                "default_value": None,
            },
        ],
        "imports_extra": ["jakarta.validation.constraints.NotBlank"],
        "javadoc_summary": "Typed configuration properties for the Adverxo bidder.",
    }


class TestConfigurationPropertiesJ2(unittest.TestCase):
    """Tests for templates/configuration-properties.java.j2."""

    def test_renders_adverxo_typed_subclass(self):
        rendered = _render("configuration-properties.java.j2", _adverxo_typed_config_ctx())
        self.assertIn("public class AdverxoBidderConfigurationProperties extends BidderConfigurationProperties", rendered)
        self.assertIn("@Data", rendered)
        self.assertIn("@NoArgsConstructor", rendered)
        self.assertIn("@EqualsAndHashCode(callSuper = true)", rendered)

    def test_validation_annotations_emitted(self):
        rendered = _render("configuration-properties.java.j2", _adverxo_typed_config_ctx())
        # Both fields carry @NotBlank.
        self.assertEqual(rendered.count("@NotBlank"), 2)
        self.assertIn("private String auctionEndpoint;", rendered)
        self.assertIn("private String registrationEndpoint;", rendered)

    def test_field_notes_emit_as_comment(self):
        rendered = _render("configuration-properties.java.j2", _adverxo_typed_config_ctx())
        self.assertIn("// Endpoint for the auction call", rendered)

    def test_default_value_emits_initializer(self):
        ctx = _adverxo_typed_config_ctx()
        ctx["typed_fields"][0]["default_value"] = '"https://default.example.com/auction"'
        rendered = _render("configuration-properties.java.j2", ctx)
        self.assertIn(
            'private String auctionEndpoint = "https://default.example.com/auction";',
            rendered,
        )

    def test_no_validation_annotations_when_absent(self):
        ctx = _adverxo_typed_config_ctx()
        ctx["typed_fields"][0]["validation_annotations"] = None
        ctx["typed_fields"][1]["validation_annotations"] = None
        ctx["imports_extra"] = []
        rendered = _render("configuration-properties.java.j2", ctx)
        self.assertNotIn("@NotBlank", rendered)
        self.assertNotIn("import jakarta.validation.constraints.NotBlank;", rendered)

    def test_extends_bidderconfigurationproperties_imported(self):
        rendered = _render("configuration-properties.java.j2", _adverxo_typed_config_ctx())
        self.assertIn(
            "import org.prebid.server.spring.config.bidder.model.BidderConfigurationProperties;",
            rendered,
        )


class TestBidderJ2(unittest.TestCase):
    """Tests for templates/bidder.java.j2 — the heaviest port-go2java template."""

    def test_renders_kobler_well_formed(self):
        rendered = _render("bidder.java.j2", _kobler_bidder_ctx())
        self.assertIn("package org.prebid.server.bidder.kobler;", rendered)
        self.assertIn("public class KoblerBidder implements Bidder<BidRequest>", rendered)

    def test_currency_conversion_field_present(self):
        rendered = _render("bidder.java.j2", _kobler_bidder_ctx())
        self.assertIn("private final CurrencyConversionService currencyConversionService;", rendered)
        self.assertIn(
            "this.currencyConversionService = Objects.requireNonNull(currencyConversionService);",
            rendered,
        )

    def test_currency_conversion_omitted_when_unused(self):
        ctx = _kobler_bidder_ctx()
        ctx["uses_currency_conversion"] = False
        rendered = _render("bidder.java.j2", ctx)
        self.assertNotIn("CurrencyConversionService", rendered)
        self.assertNotIn("currencyConversionService", rendered)

    def test_type_reference_uppercase_constant(self):
        """ExtPrebid type-reference constant uses upper-case bidder root."""
        rendered = _render("bidder.java.j2", _kobler_bidder_ctx())
        self.assertIn(
            "private static final TypeReference<ExtPrebid<?, ExtImpKobler>> KOBLER_EXT_TYPE_REFERENCE =",
            rendered,
        )

    def test_endpoint_url_validated_in_constructor(self):
        rendered = _render("bidder.java.j2", _kobler_bidder_ctx())
        self.assertIn(
            "this.endpointUrl = HttpUtil.validateUrl(Objects.requireNonNull(endpointUrl));",
            rendered,
        )

    def test_canonical_helpers_emit_when_rule_30_applies(self):
        """Rule 30 'canonical-helpers' maps to Java's framework-default behavior:
        the HTTP layer handles 204 and non-200 before makeBids is invoked, so
        the template emits NO explicit status-check code (matches upstream
        KoblerBidder.makeBids; F-new-90 retired the non-existent
        BidderUtil.isResponseStatusCodeNoContent / .checkResponseStatusCode
        method calls our earlier template had emitted).
        """
        rendered = _render("bidder.java.j2", _kobler_bidder_ctx())
        self.assertNotIn("BidderUtil.isResponseStatusCodeNoContent", rendered)
        self.assertNotIn("BidderUtil.checkResponseStatusCode", rendered)
        # Emit should explain WHY there's no explicit status check (review-readability).
        self.assertIn("Rule 30 (canonical-helpers)", rendered)
        # mapper.decodeValue must still wire through (the bid-response parsing path)
        self.assertIn("mapper.decodeValue(httpCall.getResponse().getBody()", rendered)

    def test_legacy_raw_status_when_rule_30_inapplicable(self):
        ctx = _kobler_bidder_ctx()
        ctx["http_status_kind"] = "legacy-raw"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("response.getStatusCode() == 204", rendered)
        self.assertIn("response.getStatusCode() != 200", rendered)
        self.assertNotIn("isResponseStatusCodeNoContent", rendered)

    def test_per_imp_batching_loops_through_imps(self):
        """Per-imp batching emits a per-imp loop with toBuilder rebuild.
        F-new-78 introduced an indirection: the loop body builds a `modifiedImp`
        local (which equals `imp` when ctx.entity_strategies is absent, or
        gains a `.toBuilder()...build()` mutation chain when present), and the
        per-imp request wraps `modifiedImp` rather than `imp` directly.
        """
        ctx = _kobler_bidder_ctx()
        ctx["batching_kind"] = "per-imp"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("for (Imp imp : bidRequest.getImp())", rendered)
        self.assertIn(".imp(Collections.singletonList(modifiedImp))", rendered)
        # No entity_strategies in test ctx → modifiedImp falls back to imp
        self.assertIn("final Imp modifiedImp = imp;", rendered)

    def test_max_imps_emits_chunker_helper(self):
        ctx = _kobler_bidder_ctx()
        ctx["batching_kind"] = "max-imps-per-request"
        ctx["batching_max_imps"] = 5
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("final int maxImpsPerRequest = 5;", rendered)
        self.assertIn("private static List<List<Imp>> chunkImps(", rendered)

    def test_unsupported_batching_kind_emits_throw(self):
        ctx = _kobler_bidder_ctx()
        ctx["batching_kind"] = "format-split"  # not yet template-mapped
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn(
            'throw new UnsupportedOperationException("batching_kind=format-split not yet implemented");',
            rendered,
        )

    def test_imp_mediatype_introspection_emits_imp_walk(self):
        rendered = _render("bidder.java.j2", _kobler_bidder_ctx())
        self.assertIn("if (imp.getVideo() != null)", rendered)
        self.assertIn("if (imp.getXNative() != null)", rendered)


class TestBidderTestJ2(unittest.TestCase):
    """Tests for templates/bidder-test.java.j2."""

    def test_renders_kobler_bidder_test_class(self):
        rendered = _render("bidder-test.java.j2", _kobler_bidder_test_ctx())
        self.assertIn("package org.prebid.server.bidder.kobler;", rendered)
        self.assertIn("public class KoblerBidderTest extends VertxTest", rendered)
        self.assertIn('private static final String ENDPOINT_URL = "https://test.endpoint.com/";', rendered)

    def test_setup_uses_currency_when_present(self):
        rendered = _render("bidder-test.java.j2", _kobler_bidder_test_ctx())
        self.assertIn("mock(CurrencyConversionService.class)", rendered)
        self.assertIn(
            "new KoblerBidder(ENDPOINT_URL, currencyConversionService, jacksonMapper)",
            rendered,
        )

    def test_setup_omits_currency_when_unused(self):
        ctx = _kobler_bidder_test_ctx()
        ctx["uses_currency_conversion"] = False
        rendered = _render("bidder-test.java.j2", ctx)
        self.assertNotIn("CurrencyConversionService", rendered)
        self.assertNotIn("mock(", rendered)
        self.assertIn(
            "new KoblerBidder(ENDPOINT_URL, jacksonMapper);",
            rendered,
        )

    def test_baseline_test_methods_present(self):
        """The four canonical baseline @Test methods (constructor invariants,
        204 no-content, malformed-response error, valid single-bid) all emit."""
        rendered = _render("bidder-test.java.j2", _kobler_bidder_test_ctx())
        self.assertIn("public void creationShouldFailOnInvalidEndpointUrl()", rendered)
        self.assertIn("public void makeBidsShouldReturnEmptyResultOn204NoContent()", rendered)
        self.assertIn("public void makeBidsShouldReturnErrorOnMalformedResponse()", rendered)
        self.assertIn("public void makeBidsShouldReturnSingleBannerBidForCanonicalResponse()", rendered)

    def test_scenario_methods_emit_with_todo_body(self):
        rendered = _render("bidder-test.java.j2", _kobler_bidder_test_ctx())
        self.assertIn(
            "public void makeHttpRequestsShouldUseDevEndpointWhenTestFlagIsSet()",
            rendered,
        )
        self.assertIn("// kobler dev-prod-toggle test scenario", rendered)
        self.assertIn("// TODO[port-go2java]: operator fills body", rendered)

    def test_givenbidrequest_helper_emits_imp_ext_fields(self):
        """The single field "test" with default value "true" should appear
        in ExtImpKobler.of(...). F-new-61 LineLength wrap may split the
        constructor's args onto the next line — assert call + arg are
        proximate (within 100 chars), not strict same-line equality.
        """
        rendered = _render("bidder-test.java.j2", _kobler_bidder_test_ctx())
        idx = rendered.find("ExtImpKobler.of(")
        self.assertGreater(idx, 0, "ExtImpKobler.of( call must be emitted")
        # The default value should be within the call's arg span (~100 char window)
        self.assertIn("true", rendered[idx:idx + 100])


class TestItTestJ2(unittest.TestCase):
    """Tests for templates/it-test.java.j2."""

    def test_renders_kobler_it_class(self):
        rendered = _render("it-test.java.j2", _kobler_it_test_ctx())
        self.assertIn("package org.prebid.server.it;", rendered)
        self.assertIn("public class KoblerTest extends IntegrationTest", rendered)

    def test_test_property_source_uses_localhost(self):
        rendered = _render("it-test.java.j2", _kobler_it_test_ctx())
        self.assertIn(
            'adapters.kobler.endpoint=http://localhost:8090/kobler-exchange',
            rendered,
        )

    def test_endpoint_class_imported(self):
        """D2-B1: emitted IT class references Endpoint.openrtb2_auction;
        without `import org.prebid.server.model.Endpoint;` mvn compile
        fails. Verified upstream KoblerTest/AaxTest/AdkernelAdnTest all
        carry this import."""
        rendered = _render("it-test.java.j2", _kobler_it_test_ctx())
        self.assertIn("import org.prebid.server.model.Endpoint;", rendered)
        # The usage must be present (else why import).
        self.assertIn("Endpoint.openrtb2_auction", rendered)

    def test_scenario_method_emits_with_wiremock_stub(self):
        """F-new-61 LineLength wrap split jsonFrom("<long-path>") across two
        lines (the fixture-path string literal goes on the next line at
        24-char indent). Assert the call + the fixture path are present;
        don't require them on the same line.
        """
        rendered = _render("it-test.java.j2", _kobler_it_test_ctx())
        self.assertIn("public void openrtb2AuctionShouldRespondWithBidsFromKoblerBidder()", rendered)
        self.assertIn('post(urlPathEqualTo("/kobler-exchange"))', rendered)
        self.assertIn("jsonFrom(", rendered)
        self.assertIn('"openrtb2/kobler/test-kobler-bid-request.json"', rendered)

    def test_single_seat_uses_singletonlist(self):
        rendered = _render("it-test.java.j2", _kobler_it_test_ctx())
        self.assertIn("import static java.util.Collections.singletonList;", rendered)
        self.assertIn('singletonList("kobler")', rendered)
        self.assertNotIn("import static java.util.Arrays.asList;", rendered)

    def test_multi_seat_uses_aslist(self):
        ctx = _kobler_it_test_ctx()
        ctx["scenarios"][0]["expected_seats"] = ["kobler", "kobler_alt"]
        rendered = _render("it-test.java.j2", ctx)
        self.assertIn("import static java.util.Arrays.asList;", rendered)
        self.assertIn('asList("kobler", "kobler_alt")', rendered)

    def test_multiple_scenarios_emit(self):
        ctx = _kobler_it_test_ctx()
        ctx["scenarios"].append({
            "method_name": "openrtb2AuctionShouldHandleNoBidGracefully",
            "summary": "no-bid scenario",
            "bid_request_path": "openrtb2/kobler/test-kobler-nobid-request.json",
            "bid_response_path": "openrtb2/kobler/test-kobler-nobid-response.json",
            "auction_request_path": "openrtb2/kobler/test-auction-kobler-nobid-request.json",
            "auction_response_path": "openrtb2/kobler/test-auction-kobler-nobid-response.json",
            "expected_seats": ["kobler"],
        })
        rendered = _render("it-test.java.j2", ctx)
        # Count method-level @Test annotations only (not @TestPropertySource).
        method_test_count = sum(
            1 for ln in rendered.splitlines() if ln.strip() == "@Test"
        )
        self.assertEqual(method_test_count, 2)
        self.assertIn("openrtb2AuctionShouldHandleNoBidGracefully", rendered)


class TestItFixturesJ2(unittest.TestCase):
    """Tests for the four IT-fixture JSON templates."""

    def test_auction_request_renders_well_formed_json(self):
        rendered = _render("it-fixture-auction-request.json.j2", _kobler_auction_request_ctx())
        parsed = json.loads(rendered)
        self.assertEqual(parsed["id"], "kobler-banner-1")
        self.assertEqual(parsed["tmax"], 5000)
        self.assertEqual(parsed["cur"], ["USD"])
        self.assertEqual(len(parsed["imp"]), 1)
        imp = parsed["imp"][0]
        self.assertEqual(imp["id"], "imp-1")
        self.assertEqual(imp["banner"]["format"], [{"w": 300, "h": 250}])
        self.assertEqual(imp["ext"]["prebid"]["bidder"]["kobler"]["test"], True)
        self.assertIn("site", parsed)
        self.assertNotIn("app", parsed)

    def test_auction_request_app_branch(self):
        ctx = _kobler_auction_request_ctx()
        ctx["site_page"] = None
        ctx["app_bundle"] = "com.example.app"
        rendered = _render("it-fixture-auction-request.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertNotIn("site", parsed)
        self.assertEqual(parsed["app"]["bundle"], "com.example.app")

    def test_bid_request_flatten_imp_ext(self):
        ctx = _kobler_auction_request_ctx()
        ctx["flatten_imp_ext"] = True
        rendered = _render("it-fixture-bid-request.json.j2", ctx)
        parsed = json.loads(rendered)
        # Adapter typically flattens imp.ext.prebid.bidder.{bidder} → imp.ext.bidder.
        self.assertIn("bidder", parsed["imp"][0]["ext"])
        self.assertNotIn("prebid", parsed["imp"][0]["ext"])
        self.assertEqual(parsed["imp"][0]["ext"]["bidder"]["test"], True)

    def test_bid_response_renders_well_formed_json(self):
        rendered = _render("it-fixture-bid-response.json.j2", _kobler_bid_response_ctx())
        parsed = json.loads(rendered)
        self.assertEqual(parsed["id"], "kobler-resp-1")
        self.assertEqual(parsed["cur"], "USD")
        self.assertEqual(len(parsed["seatbid"]), 1)
        seat = parsed["seatbid"][0]
        self.assertEqual(seat["seat"], "kobler")
        self.assertEqual(len(seat["bid"]), 1)
        bid = seat["bid"][0]
        self.assertEqual(bid["price"], 1.5)
        self.assertEqual(bid["adomain"], ["advertiser.example.com"])
        self.assertNotIn("cat", bid)  # null in ctx → omitted

    def test_auction_response_includes_ext_prebid(self):
        rendered = _render("it-fixture-auction-response.json.j2", _kobler_auction_response_ctx())
        parsed = json.loads(rendered)
        bid = parsed["seatbid"][0]["bid"][0]
        self.assertEqual(bid["ext"]["prebid"]["type"], "banner")
        self.assertEqual(bid["ext"]["prebid"]["meta"]["origbidcpm"], 1.5)

    def test_auction_response_omits_meta_when_no_currency_conversion(self):
        ctx = _kobler_auction_response_ctx()
        ctx["bids"][0]["ext_origbidcpm"] = None
        ctx["bids"][0]["ext_origbidcur"] = None
        rendered = _render("it-fixture-auction-response.json.j2", ctx)
        parsed = json.loads(rendered)
        bid = parsed["seatbid"][0]["bid"][0]
        self.assertNotIn("meta", bid["ext"]["prebid"])


class TestRequiredArtifacts(unittest.TestCase):
    """Sanity: every Java template referenced by SKILL.md Step 5 either exists
    or is flagged in the templates STUB.md as a future deliverable."""

    EXPECTED_TEMPLATES = (
        "bidder-config.yaml.j2",                 # D2.1 commit
        "ext-imp-pojo.java.j2",                  # D2.2 commit
        "configuration.java.j2",                 # D2.2 commit
        "configuration-properties.java.j2",      # D2.3 commit
        "bidder.java.j2",                        # D2.4 commit (heaviest template)
        "bidder-test.java.j2",                   # D2.5 commit
        "it-test.java.j2",                       # D2.6 commit
        "it-fixture-auction-request.json.j2",    # D2.7 commit
        "it-fixture-auction-response.json.j2",   # D2.7 commit
        "it-fixture-bid-request.json.j2",        # D2.7 commit
        "it-fixture-bid-response.json.j2",       # D2.7 commit
        # All 11 templates shipped after D2.7.
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
