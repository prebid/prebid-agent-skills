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

    def test_modifying_vast_xml_explicit_false_when_false(self):
        """Rule 49 / F-new-105. The two frameworks disagree on what an absent
        key means, so a Go-effective `false` MUST be declared explicitly in the
        Java emission.

        Upstream at e3ffd57db: `src/main/resources/application.yaml:102` sets
        `adapter-defaults: modifying-vast-xml-allowed: true`, back-filled by
        `BidderConfigurationProperties.init()` at lines 67-68 through
        `ObjectUtils.defaultIfNull`; Go's `config/bidderinfo.go:35` declares a
        plain `bool`, so absent means false there. Omitting the key therefore
        flips VastModifier on for every video bid.

        The test this replaced asserted the key was omitted, reasoning from
        upstream kobler's own bidder-config carrying no such key. True of that
        file, wrong for a port: kobler-the-Java-adapter was never ported FROM a
        Go-effective-false source by this skill."""
        rendered = _render("bidder-config.yaml.j2", _kobler_ctx())
        parsed = yaml.safe_load(rendered)
        self.assertIs(parsed["adapters"]["kobler"]["modifying-vast-xml-allowed"], False)

    def test_modifying_vast_xml_explicit_true_when_true(self):
        """Emitted in both polarities. Explicit `true` has live upstream
        precedent (aax, freewheelssp, mediasquare, vungle all declare it)."""
        ctx = _kobler_ctx()
        ctx["modifying_vast_xml"] = True
        rendered = _render("bidder-config.yaml.j2", ctx)
        parsed = yaml.safe_load(rendered)
        self.assertIs(parsed["adapters"]["kobler"]["modifying-vast-xml-allowed"], True)

    def test_modifying_vast_xml_absent_from_ctx_fails_loudly(self):
        """Not defaulted. A missing ctx key would render `false`, which is
        indistinguishable from a deliberate declaration -- and `false` is the
        polarity that is wrong to guess, because it is Java's non-default."""
        ctx = _kobler_ctx()
        del ctx["modifying_vast_xml"]
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("bidder-config.yaml.j2", ctx)
        self.assertIn("rule49_modifying_vast_xml_is_required", str(cm.exception))

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
        """The factory and the deps bean both take the typed subclass.

        Renamed from the *BidderConfigurationProperties form the old separate-file
        template used: no upstream bidder uses that suffix, which names the two
        framework classes `model/BidderConfigurationProperties` and
        `model/DefaultBidderConfigurationProperties`.
        """
        rendered = _render("configuration.java.j2", _adverxo_typed_config_ctx())
        self.assertIn("AdverxoConfigurationProperties configurationProperties()", rendered)
        self.assertIn("return new AdverxoConfigurationProperties();", rendered)
        self.assertIn("AdverxoConfigurationProperties adverxoConfigurationProperties,", rendered)

    def test_property_source_matches_bidder_config_path(self):
        rendered = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertIn(
            'classpath:/bidder-config/kobler.yaml',
            rendered,
        )

    def test_bidderconfigurationproperties_import_is_always_used(self):
        """Guards the same thing the old drop-it rule guarded: no unused import.

        The rule inverted when the Rule 35 subclass moved from a separate file
        into this one. It used to be dropped under Rule 35 because nothing here
        referenced it and checkstyle UnusedImports would flag it. Now the nested
        subclass `extends BidderConfigurationProperties`, and without Rule 35 the
        factory method returns it -- so it is referenced in BOTH arms and must be
        imported in both. Dropping it now would not compile.
        """
        IMPORT = "import org.prebid.server.spring.config.bidder.model.BidderConfigurationProperties;"
        plain = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertIn(IMPORT, plain)
        self.assertIn("BidderConfigurationProperties configurationProperties()", plain)

        typed = _render("configuration.java.j2", _adverxo_typed_config_ctx())
        self.assertIn(IMPORT, typed)
        self.assertIn("extends BidderConfigurationProperties", typed)

    def test_validated_tracks_constraints_not_rule_35(self):
        """The trigger changed, and the old one over-emitted.

        @Validated used to be emitted whenever Rule 35 fired, and onto the @Bean
        factory method. Upstream puts it on the CLASS and only where a field
        carries a jakarta constraint: 7 of the 16 Rule-35 subclasses have it and
        every one of those has a constraint; none has it without one. It is
        redundant either way -- the parent BidderConfigurationProperties is
        @Validated and spring resolves it up the type hierarchy -- so emitting it
        on an unconstrained subclass is noise no upstream file carries.
        """
        std = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertNotIn("@Validated", std)
        self.assertNotIn("import org.springframework.validation.annotation.Validated;", std)

        ctx = _adverxo_typed_config_ctx()
        ctx["typed_fields"] = [dict(f, validation_annotations=None) for f in ctx["typed_fields"]]
        ctx["typed_config_constraint_imports"] = None
        unconstrained = _render("configuration.java.j2", ctx)
        self.assertIn("private static class", unconstrained)
        self.assertNotIn("@Validated", unconstrained)

    def test_rule_35_without_typed_fields_fails_loudly(self):
        """A ctx claiming Rule 35 fired but carrying no fields is a caller bug.

        Before the guard this rendered a subclass with an empty body -- a Rule 35
        class binding none of the properties Rule 35 exists to bind -- and
        reported success.
        """
        ctx = _kobler_configuration_ctx()
        ctx["has_typed_config_props"] = True
        ctx["typed_config_class_name"] = "KoblerConfigurationProperties"
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("configuration.java.j2", ctx)
        self.assertIn("typed_fields_is_empty", str(cm.exception))

    def test_typed_fields_without_the_flag_fails_loudly(self):
        """The other direction: fields supplied, flag false, fields dropped."""
        ctx = _adverxo_typed_config_ctx()
        ctx["has_typed_config_props"] = False
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("configuration.java.j2", ctx)
        self.assertIn("would_be_dropped", str(cm.exception))

    def test_never_emits_deleted_usersyncer_creator(self):
        """`UsersyncerCreator` was deleted upstream in 2880782f (#4464,
        2026-07-09); `BidderDepsAssembler` never had a `usersyncerCreator`
        method. Emitting either does not compile. The Usersyncer is derived
        internally from the bound properties, so a bidder WITH usersync still
        gets no argument for it — canonical: AdprimeConfiguration.java, whose
        bidder-config declares iframe+redirect usersync."""
        ctx = _kobler_configuration_ctx()
        ctx["user_sync"] = {
            "cookie_family_name": "kobler",
            "iframe": {"url": "https://sync.example.com?redir={redirect_url}"},
        }
        rendered = _render("configuration.java.j2", ctx)
        self.assertNotIn("UsersyncerCreator", rendered)
        self.assertNotIn("usersyncerCreator", rendered)
        self.assertIn(".withConfig(koblerConfigurationProperties)", rendered)
        self.assertIn(".bidderCreator(", rendered)

    def test_external_url_param_gated_on_endpoint_macro(self):
        """`external-url` is an endpoint-macro concern, not a usersync one:
        4 of 255 upstream configs take it, all to resolve
        {PREBID_SERVER_ENDPOINT} (canonical: AaxConfiguration.java). Absent the
        flag, the parameter and BOTH of its imports must be omitted, or
        checkstyle UnusedImports fails the build."""
        without = _render("configuration.java.j2", _kobler_configuration_ctx())
        self.assertNotIn("externalUrl", without)
        self.assertNotIn("import org.springframework.beans.factory.annotation.Value;", without)
        self.assertNotIn("jakarta", without)

        ctx = _kobler_configuration_ctx()
        ctx["endpoint_external_url_macro"] = True
        with_macro = _render("configuration.java.j2", ctx)
        self.assertIn('@NotBlank @Value("${external-url}") String externalUrl,', with_macro)
        self.assertIn("import org.springframework.beans.factory.annotation.Value;", with_macro)
        # ImportOrder groups="*,/^java|^jakarta/" — jakarta sits in the LAST group.
        lines = with_macro.splitlines()
        jakarta_at = next(i for i, l in enumerate(lines) if l.startswith("import jakarta."))
        last_star_at = max(i for i, l in enumerate(lines) if l.startswith("import org."))
        self.assertGreater(jakarta_at, last_star_at)
        self.assertEqual("", lines[jakarta_at - 1], "jakarta group must be blank-line separated")


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
    """Rule 35 context for configuration.java.j2's nested-subclass arm.

    Was the input to configuration-properties.java.j2, which emitted a separate
    file. Same field data; the subclass is now nested, so the context also
    carries the Configuration class's own inputs.
    """
    return {
        "bidder_name": "adverxo",
        "bidder_class_root": "Adverxo",
        "uses_currency_conversion": False,
        "has_typed_config_props": True,
        "typed_config_class_name": "AdverxoConfigurationProperties",
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
        "typed_config_constraint_imports": ["jakarta.validation.constraints.NotBlank"],
        "typed_config_javadoc": "Typed configuration properties for the Adverxo bidder.",
        "config_class_name": None,
        "extra_constructor_args": None,
        "bidder_creator_extra_args": None,
        "user_sync": None,
        "endpoint_external_url_macro": False,
        "javadoc_summary": None,
    }


class TestRule35NestedSubclass(unittest.TestCase):
    """The Rule 35 subclass is emitted NESTED, in the upstream shape.

    It used to be a separate {Bidder}BidderConfigurationProperties.java. All 16
    Rule-35 subclasses at e3ffd57 are nested inside their {Bidder}Configuration
    (15 of them `private static`), none is a separate file, and no bidder uses
    the *BidderConfigurationProperties suffix -- that names two framework
    classes. A PR shipping the separate form would arrive in a shape the Java
    reviewer has no upstream precedent for.
    """

    def _render_typed(self, **overrides):
        ctx = _adverxo_typed_config_ctx()
        ctx.update(overrides)
        return _render("configuration.java.j2", ctx)

    def test_subclass_is_nested_private_static_in_the_configuration_class(self):
        rendered = self._render_typed()
        self.assertIn(
            "    private static class AdverxoConfigurationProperties extends BidderConfigurationProperties {",
            rendered)
        self.assertIn("public class AdverxoConfiguration {", rendered)
        # Nested: the subclass opens after the Configuration class does.
        self.assertLess(rendered.index("public class AdverxoConfiguration {"),
                        rendered.index("private static class AdverxoConfigurationProperties"))

    def test_no_separate_file_suffix_is_emitted(self):
        """The suffix that collides with model/BidderConfigurationProperties."""
        self.assertNotIn("AdverxoBidderConfigurationProperties", self._render_typed())

    def test_annotation_order_matches_all_sixteen_upstream_subclasses(self):
        rendered = self._render_typed()
        order = [rendered.index(a) for a in
                 ("@Validated", "@Data", "@EqualsAndHashCode(callSuper = true)", "@NoArgsConstructor")]
        self.assertEqual(order, sorted(order), "expected @Validated @Data @EqualsAndHashCode @NoArgsConstructor")

    def test_validated_only_when_a_field_carries_a_constraint(self):
        """Redundant with the parent's @Validated, but the house form on a
        constrained subclass: 7 of 16 carry it and all 7 have a constraint."""
        constrained = self._render_typed()
        self.assertIn("@Validated", constrained)
        self.assertIn("import org.springframework.validation.annotation.Validated;", constrained)

        fields = [dict(f, validation_annotations=None)
                  for f in _adverxo_typed_config_ctx()["typed_fields"]]
        plain = self._render_typed(typed_fields=fields, typed_config_constraint_imports=None)
        self.assertNotIn("@Validated", plain)
        self.assertNotIn("import org.springframework.validation.annotation.Validated;", plain)

    def test_validation_annotations_and_fields_emitted(self):
        rendered = self._render_typed()
        self.assertEqual(rendered.count("@NotBlank"), 2)
        self.assertIn("        private String auctionEndpoint;", rendered)
        self.assertIn("        private String registrationEndpoint;", rendered)

    def test_field_notes_emit_as_comment(self):
        self.assertIn("// Endpoint for the auction call", self._render_typed())

    def test_default_value_emits_initializer(self):
        fields = _adverxo_typed_config_ctx()["typed_fields"]
        fields[0] = dict(fields[0], default_value='"https://default.example.com/auction"')
        self.assertIn('private String auctionEndpoint = "https://default.example.com/auction";',
                      self._render_typed(typed_fields=fields))

    def test_lombok_and_parent_imported_only_when_the_subclass_exists(self):
        rendered = self._render_typed()
        for imp in ("import lombok.Data;", "import lombok.EqualsAndHashCode;",
                    "import lombok.NoArgsConstructor;",
                    "import org.prebid.server.spring.config.bidder.model.BidderConfigurationProperties;"):
            self.assertIn(imp, rendered)
        plain = self._render_typed(has_typed_config_props=False, typed_config_class_name=None,
                                   typed_fields=None, typed_config_constraint_imports=None,
                                   typed_config_javadoc=None)
        self.assertNotIn("import lombok.", plain)
        self.assertNotIn("private static class", plain)

    def test_jakarta_import_is_not_duplicated_with_the_external_url_macro(self):
        """Both the macro parameter and a constrained field want @NotBlank."""
        rendered = self._render_typed(endpoint_external_url_macro=True)
        self.assertEqual(1, rendered.count("import jakarta.validation.constraints.NotBlank;"))

    def test_configuration_properties_prefix_is_a_literal(self):
        """0 of 255 upstream files concatenate the constant into the prefix."""
        rendered = self._render_typed()
        self.assertIn('@ConfigurationProperties("adapters.adverxo")', rendered)
        self.assertNotIn('"adapters." + BIDDER_NAME', rendered)


class TestTypedConfigTypeWitness(unittest.TestCase):
    """`BidderDepsAssembler.<Props>forBidder` -- required, not stylistic.

    `forBidder` is `<CFG extends BidderConfigurationProperties>
    BidderDepsAssembler<CFG>`. With no witness CFG infers to the bound, so the
    bidderCreator's function parameter is a plain BidderConfigurationProperties
    and any subclass getter read off it does not resolve.

    Grounded by compiling the upstream tree at e3ffd57 rather than by matching
    it: all 12 witness-carrying configs compile unmodified, and all 12 fail with
    only `.<Props>` removed (Magnite 6 errors, the rest 1 each). Adding a witness
    to the 4 bare Rule-35 configs leaves them at 0 errors, so bare is the
    minimal form, not a requirement -- which is why the population count
    (243/255 bare) cannot decide this and the declared getters must.
    """

    def _typed(self, **overrides):
        ctx = _adverxo_typed_config_ctx()
        ctx.update(overrides)
        return _render("configuration.java.j2", ctx)

    def test_witness_emitted_when_the_creator_reads_a_typed_getter(self):
        rendered = self._typed(typed_config_lambda_getters=["auctionEndpoint"])
        self.assertIn("BidderDepsAssembler.<AdverxoConfigurationProperties>forBidder(BIDDER_NAME)",
                      rendered)

    def test_no_witness_when_no_typed_getter_is_declared(self):
        """The corpus default. 243 of 255 upstream configs are bare."""
        rendered = self._typed()
        self.assertIn("BidderDepsAssembler.forBidder(BIDDER_NAME)", rendered)
        self.assertNotIn("BidderDepsAssembler.<", rendered)

    def test_declared_getters_are_threaded_into_the_creator_call(self):
        """Emitting the witness without the read, or the read without the
        witness, is what does not compile -- so one ctx key drives both."""
        rendered = self._typed(typed_config_lambda_getters=["auctionEndpoint",
                                                           "registrationEndpoint"])
        self.assertIn("config.getEndpoint(), config.getAuctionEndpoint(), "
                      "config.getRegistrationEndpoint()", rendered)

    def test_witness_and_getter_reads_are_emitted_together(self):
        """The coupling is the invariant: every rendering either has both or
        neither. A rendering with one is the shape javac rejects."""
        for getters in ([], ["auctionEndpoint"], ["auctionEndpoint", "registrationEndpoint"]):
            rendered = self._typed(typed_config_lambda_getters=getters)
            has_witness = "BidderDepsAssembler.<" in rendered
            has_reads = "config.getAuctionEndpoint()" in rendered
            self.assertEqual(has_witness, has_reads,
                             f"witness={has_witness} reads={has_reads} for {getters}")

    def test_witness_type_defaults_to_the_bidder_root_suffix(self):
        rendered = self._typed(typed_config_class_name=None,
                               typed_config_lambda_getters=["auctionEndpoint"])
        self.assertIn("BidderDepsAssembler.<AdverxoConfigurationProperties>forBidder", rendered)

    def test_getters_without_a_subclass_is_a_hard_error(self):
        """There is no subclass to read them from, so the emission would not
        compile. Fail at render rather than hand a reviewer broken Java.

        typed_fields is cleared so the neighbouring
        `typed_fields_supplied_but_has_typed_config_props_is_false` guard cannot
        fire first -- its message also contains has_typed_config_props, so a
        substring assertion passes while this guard is absent.
        """
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            self._typed(has_typed_config_props=False, typed_fields=None,
                        typed_config_constraint_imports=None, typed_config_javadoc=None,
                        typed_config_lambda_getters=["auctionEndpoint"])
        self.assertIn("ERROR_typed_config_lambda_getters_requires_has_typed_config_props",
                      str(cm.exception))

    def test_a_config_getter_in_free_form_extra_args_is_a_hard_error(self):
        """bidder_creator_extra_args is pasted through verbatim, so a subclass
        getter hidden in it needs the witness the template was not told to
        emit. Upstream Magnite is this shape: 4 typed reads in the creator."""
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            self._typed(bidder_creator_extra_args="config.getAuctionEndpoint()")
        self.assertIn("ERROR_bidder_creator_extra_args_reads_a_config_getter",
                      str(cm.exception))

    def test_extra_args_without_a_config_getter_still_renders(self):
        """The guard must not fire on args that read something else."""
        rendered = self._typed(bidder_creator_extra_args="versionInfo.getVersion()")
        self.assertIn("versionInfo.getVersion()", rendered)


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

    def test_no_status_check_is_emitted_whatever_the_source_declared(self):
        """Rule 30: "A porter Go->Java should NOT include explicit status checks
        (Java framework handles it)." HttpBidderRequester turns NO_CONTENT into an
        empty result and any non-200 into badServerResponse before makeBids is
        invoked (HttpBidderRequester.java:303 and :322), and 0 of the 254 upstream
        Java bidders reference a status code.

        This held for the alias `canonical-helpers` only. Both spellings a Go
        source spec actually carries -- `canonical-go-helpers` and `legacy-raw-go`
        (behavior-taxonomy.md) -- fell through to a hand-rolled
        `response.getStatusCode() == 204` / `!= 200` pair, so a Go adapter using
        the canonical helpers ported to a Java bidder that hand-rolls the checks:
        a shape with zero corpus precedent, emitted for every real input.
        """
        for kind in ("canonical-go-helpers", "canonical-helpers", "legacy-raw-go",
                     "framework-default", "framework-default-plus-empty-seatbid-shortcircuit",
                     None):
            ctx = _kobler_bidder_ctx()
            ctx["http_status_kind"] = kind
            rendered = _render("bidder.java.j2", ctx)
            self.assertNotIn("getStatusCode()", rendered, f"kind={kind}")
            self.assertNotIn("BidderUtil.isResponseStatusCodeNoContent", rendered)
            self.assertNotIn("BidderUtil.checkResponseStatusCode", rendered)
            # The emission has to say WHY there is no check, or a reviewer reads
            # the absence as an omission.
            self.assertIn("Rule 30: no explicit status check", rendered, f"kind={kind}")

    def test_a_bespoke_status_policy_gets_a_todo_not_an_invented_check(self):
        """`custom-status-checks` / `custom` are the only kinds that put anything
        in the bidder, and they get a TODO: there is no Java shape to copy, so
        transcribing the Go branches would invent one."""
        for kind in ("custom-status-checks", "custom"):
            ctx = _kobler_bidder_ctx()
            ctx["http_status_kind"] = kind
            rendered = _render("bidder.java.j2", ctx)
            self.assertIn("TODO[port-go2java]", rendered, kind)
            self.assertIn(kind, rendered, kind)
            self.assertNotIn("getStatusCode()", rendered, kind)

    def test_an_unknown_status_kind_is_a_hard_error(self):
        """Falling through on an unrecognised value is how the alias mismatch
        stayed invisible. `legacy-raw` was named in the Inputs block and consumed
        by no branch."""
        for bad in ("legacy-raw", "canonical", "typo"):
            ctx = _kobler_bidder_ctx()
            ctx["http_status_kind"] = bad
            with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
                _render("bidder.java.j2", ctx)
            self.assertIn("ERROR_unknown_http_status_kind", str(cm.exception), bad)

    def test_the_emission_names_no_unrelated_bidder(self):
        """The status comment used to read "matches upstream KoblerBidder", which
        every emitted bidder carried whatever it was porting. It cites the
        framework file now."""
        ctx = _kobler_bidder_ctx()
        ctx["bidder_class_root"] = "Portprobe"
        ctx["imp_ext_class_root"] = "Portprobe"
        rendered = _render("bidder.java.j2", ctx)
        self.assertNotIn("KoblerBidder", rendered)
        self.assertIn("HttpBidderRequester.java:303", rendered)
        # mapper.decodeValue must still wire through (the bid-response parsing path)
        self.assertIn("mapper.decodeValue(httpCall.getResponse().getBody()", rendered)


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

    def test_by_bid_mtype_switches_on_mtype(self):
        """Teal #4765 — the correct multiformat shape resolves from the
        response's own bid.mtype (imp introspection is fallback only) and
        surfaces an error rather than silently defaulting to banner."""
        ctx = _kobler_bidder_ctx()
        ctx["bid_type_resolution"] = "by-bid-mtype"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("bid.getMtype()", rendered)
        self.assertIn("switch (mType)", rendered)
        self.assertIn("case 2 -> BidType.video;", rendered)
        self.assertIn("case 4 -> BidType.xNative;", rendered)

    def test_grouped_by_key_defaults_to_keying_on_the_whole_ext_object(self):
        """Rule 47. The default shape is what upstream does most.

        Measured at prebid-server-java e3ffd57db and prebid-server 0ba35231, the
        merged adapters that group imps key their map on:

            ExtImpAdkernel / ExtImpDatablocks / ExtImpZeroclickfraud  (whole ext)
            Integer  (adtarget)
            MediaType enum  (taboola)
            String  (thirtythreeacross)

        so the whole-ext shape is 3 of 6, and on the Go side it is 4 of 4
        (`map[openrtb_ext.ExtImpAdkernel][]openrtb2.Imp`). port-java2go already
        emits that, so defaulting to it here also makes the two port skills
        agree. An earlier revision hardcoded `Map<String, …>` keyed on one field,
        which is 1 of 6 and could not express adkernel at all.
        """
        ctx = _kobler_bidder_ctx()
        ctx["batching_kind"] = "grouped-by-key"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("final Map<ExtImpKobler, List<Imp>> impsByGroup = new HashMap<>();", rendered)
        self.assertIn("impsByGroup.computeIfAbsent(extImp, key -> new ArrayList<>())", rendered)
        self.assertIn("for (Map.Entry<ExtImpKobler, List<Imp>> groupEntry : impsByGroup.entrySet())",
                      rendered)
        # Per-imp AND per-group failures stay isolated.
        self.assertEqual(rendered.count("errors.add(BidderError.badInput(e.getMessage()));"), 2)
        self.assertNotIn("UnsupportedOperationException", rendered)

    def test_grouped_by_key_uses_hashmap_not_linkedhashmap(self):
        """All six merged Java groupers use `new HashMap<>()`; none uses
        LinkedHashMap. An earlier revision emitted LinkedHashMap and carried a
        comment calling HashMap a defect that "breaks deterministic request order
        and fixture matching" -- which Go's own harness contradicts:
        `adapters/adapterstest/test_json.go` matches requests order-insensitively
        on purpose, "as the use of maps in some adapters purposely randomizes
        order"."""
        ctx = _kobler_bidder_ctx()
        ctx["batching_kind"] = "grouped-by-key"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("new HashMap<>()", rendered)
        self.assertNotIn("LinkedHashMap", rendered)

    def test_grouped_by_key_typed_field_key(self):
        """The minority shape: key on one field, with its type carried across."""
        for key_type, field, getter in (("String", "route", "getRoute"),
                                        ("Integer", "zoneId", "getZoneId")):
            ctx = _kobler_bidder_ctx()
            ctx["batching_kind"] = "grouped-by-key"
            ctx["batching_per_key"] = {"key_field": field, "key_type": key_type}
            with self.subTest(key_type=key_type):
                rendered = _render("bidder.java.j2", ctx)
                self.assertIn(f"final Map<{key_type}, List<Imp>> impsByGroup = new HashMap<>();",
                              rendered)
                self.assertIn(f"impsByGroup.computeIfAbsent(extImp.{getter}(), "
                              f"key -> new ArrayList<>())", rendered)

    def test_typed_field_key_without_a_type_fails_loudly(self):
        """`String` cannot be assumed: adtarget keys on Integer and taboola on an
        enum, so a field key with no declared type would emit a map whose type is
        a guess. adkernel's own key is `Integer zoneId`."""
        ctx = _kobler_bidder_ctx()
        ctx["batching_kind"] = "grouped-by-key"
        ctx["batching_per_key"] = {"key_field": "zoneId"}
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("bidder.java.j2", ctx)
        self.assertIn("rule47_key_field_requires_key_type", str(cm.exception))

    def test_grouped_by_key_non_identifier_key_field_fails_loudly(self):
        """A source-side JSON field name may be snake_case or hyphenated; the
        getter derivation only works on a lower-camelCase Java identifier, so
        normalization belongs in the SKILL (Rule 46), not in a silent render."""
        for bad in ("account_id", "account-id", "AccountId", "9lives"):
            ctx = _kobler_bidder_ctx()
            ctx["batching_kind"] = "grouped-by-key"
            ctx["batching_per_key"] = {"key_field": bad, "key_type": "String"}
            with self.subTest(key_field=bad):
                with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
                    _render("bidder.java.j2", ctx)
                self.assertIn("rule47_key_field_must_be_a_lower_camelCase_java_identifier",
                              str(cm.exception))

    def test_grouping_imports_absent_for_other_batching_kinds(self):
        """The grouping imports are conditional -- checkstyle UnusedImports would
        fail the build on any other batching kind."""
        rendered = _render("bidder.java.j2", _kobler_bidder_ctx())
        self.assertNotIn("import java.util.HashMap;", rendered)
        self.assertNotIn("import java.util.Map;", rendered)

    def test_per_bid_skip_mtype_accumulates_and_continues(self):
        """F-new-108. An unresolved mtype adds badServerResponse and yields
        null; the extractBids stream filters the null so sibling bids in the
        same response survive -- the Go `errs = append(errs, err); continue`
        shape. Target-repo precedent at e3ffd57db: ZentotemBidder threads the
        errors list through extractBids -> makeBidderBid -> the type resolver,
        and 68 upstream adapters take an errors list into extractBids."""
        ctx = _kobler_bidder_ctx()
        ctx["bid_type_resolution"] = "by-bid-mtype"
        ctx["bid_type_error_tolerance"] = "per-bid-skip"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("case null, default ->", rendered)
        self.assertIn("errors.add(BidderError.badServerResponse(", rendered)
        self.assertIn("yield null;", rendered)
        self.assertIn("return Result.of(extractBids(bidResponse, errors), errors);", rendered)
        self.assertIn("private List<BidderBid> extractBids(BidResponse bidResponse, List<BidderError> errors)",
                      rendered)
        self.assertIn("private BidType resolveBidType(Bid bid, List<BidderError> errors)", rendered)
        self.assertIn("private BidderBid makeBidderBid(Bid bid, String currency, List<BidderError> errors)",
                      rendered)
        # The abort-all shape must not co-emit: two resolveBidType overloads
        # would not compile, and the throw would pre-empt the skip.
        self.assertNotIn('"Missing bid.mtype for bid with impId: "', rendered)
        self.assertNotIn("private BidType resolveBidType(Bid bid, BidRequest bidRequest)", rendered)
        self.assertNotIn("extractBids(bidResponse, bidRequest)", rendered)

    def test_per_bid_skip_requires_by_bid_mtype(self):
        """Only by-bid-mtype has the null-means-skip contract. Every other arm
        returns a BidType unconditionally, so the errors parameter would be
        unused and the null branch unreachable."""
        ctx = _kobler_bidder_ctx()
        ctx["bid_type_resolution"] = "imp-mediatype-introspection"
        ctx["bid_type_error_tolerance"] = "per-bid-skip"
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("bidder.java.j2", ctx)
        self.assertIn("per_bid_skip_tolerance_requires_by_bid_mtype_resolution", str(cm.exception))

    def test_abort_all_mtype_is_the_default(self):
        """Regression pin: with no tolerance flag, by-bid-mtype keeps the
        abort-all PreBidException shape (the Teal #4765 baseline)."""
        ctx = _kobler_bidder_ctx()
        ctx["bid_type_resolution"] = "by-bid-mtype"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn('"Missing bid.mtype for bid with impId: "', rendered)
        self.assertNotIn("case null, default ->", rendered)
        self.assertNotIn("makeBidderBid", rendered)
        self.assertIn("return Result.withValues(extractBids(bidResponse, bidRequest));", rendered)

    def test_multiformat_imp_introspection_fails_loudly(self):
        """A multiformat adapter cannot resolve bid type by imp introspection —
        a co-present-format imp mis-types every non-first bid. Selecting
        imp-only resolution while multiformat_supported is true MUST fail
        loudly at render rather than emit the mis-typing shape (mirrors the
        port-java2go guard)."""
        ctx = _kobler_bidder_ctx()
        ctx["multiformat_supported"] = True
        ctx["bid_type_resolution"] = "imp-mediatype-introspection"
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("bidder.java.j2", ctx)
        self.assertIn("multiformat_adapter_must_use_by_bid_mtype_resolution", str(cm.exception))

    def test_single_format_imp_introspection_still_renders(self):
        """No regression: a single-format adapter may still resolve by imp
        introspection — the guard is scoped to multiformat adapters only."""
        ctx = _kobler_bidder_ctx()
        ctx["bid_type_resolution"] = "imp-mediatype-introspection"
        rendered = _render("bidder.java.j2", ctx)
        self.assertIn("private BidType resolveBidType(", rendered)


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
        """The three canonical baseline @Test methods emit: constructor
        invariants, malformed-response error, valid single-bid.

        There is no 204 method. It used to be emitted and it asserted a Go
        semantic that cannot hold in Java -- see
        TestEmittedJavaTestsExecute.test_no_204_case_is_emitted_against_makeBids.
        """
        rendered = _render("bidder-test.java.j2", _kobler_bidder_test_ctx())
        self.assertIn("public void creationShouldFailOnInvalidEndpointUrl()", rendered)
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


class TestEmittedJavaTestsExecute(unittest.TestCase):
    """Defects found by compiling the emitted Java tests and running them.

    bidder-test.java.j2 and it-test.java.j2 had never been handed to a compiler.
    Both compile clean against upstream at e3ffd57 (javac 25.0.2, Lombok
    annotation processing on, 3093 main + 949 test classes). Executing the unit
    test surfaced one behavioural defect that no substring assertion on the
    rendered text would have caught.
    """

    def test_no_204_case_is_emitted_against_makeBids(self):
        """A Go-ism. Go hands MakeBids the status code, so a Go adapter checks
        http.StatusNoContent -- and the emitted Go bidder does. Java does not:
        HttpBidderRequester short-circuits NO_CONTENT before makeBids is invoked
        (HttpBidderRequester.java:303 and :322). The emitted test asserted an
        empty result on 204, which cannot hold -- decoding "" throws
        DecodeException and the bidder returns badServerResponse, so the emitted
        suite failed its own emitted bidder.

        Corpus: 1 of 254 upstream bidder test directories feeds 204 to makeBids
        (sparteo), and it asserts an error, not an empty result.
        """
        rendered = _render("bidder-test.java.j2", _kobler_bidder_test_ctx())
        self.assertNotIn("givenHttpCall(204", rendered)
        self.assertNotIn("204NoContent", rendered)

    def test_the_go_direction_keeps_its_204_check(self):
        """The mirror must not be 'fixed' the same way: in Go the status check
        belongs in the adapter, so removing it there would be the defect."""
        go_tpl = (REPO_ROOT / "prebid-server-go" / "port-java2go" / "templates"
                  / "bidder.go.j2").read_text()
        self.assertIn("http.StatusNoContent", go_tpl)

    def test_scenario_scaffolds_fail_by_construction(self):
        """The remaining failure in a fresh emission is deliberate: one @Test per
        fixture_inventory.exemplary[] entry whose body the operator fills. They
        fail rather than pass-vacuously, so an unfilled scaffold cannot be
        mistaken for coverage -- which is why the acceptance gate on emitted
        tests is a post-fill gate, not a property of a fresh emission."""
        ctx = _kobler_bidder_test_ctx()
        scenarios = ctx.get("scenario_methods") or []
        if not scenarios:
            self.skipTest("this ctx declares no scenario_methods")
        rendered = _render("bidder-test.java.j2", ctx)
        self.assertEqual(rendered.count("not yet implemented"), len(scenarios))
        self.assertIn("TODO[port-go2java]", rendered)


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
        "configuration.java.j2",                 # D2.2 commit; also carries the
                                                 # Rule 35 nested subclass since
                                                 # configuration-properties.java.j2
                                                 # was removed
        "bidder.java.j2",                        # D2.4 commit (heaviest template)
        "bidder-test.java.j2",                   # D2.5 commit
        "it-test.java.j2",                       # D2.6 commit
        "it-fixture-auction-request.json.j2",    # D2.7 commit
        "it-fixture-auction-response.json.j2",   # D2.7 commit
        "it-fixture-bid-request.json.j2",        # D2.7 commit
        "it-fixture-bid-response.json.j2",       # D2.7 commit
        # 10 templates. configuration-properties.java.j2 is gone: it emitted the
        # typed config subclass as a SEPARATE
        # src/main/java/.../{Bidder}BidderConfigurationProperties.java file, a shape
        # no upstream bidder uses -- all 16 Rule-35 subclasses are nested inside
        # their {Bidder}Configuration.java, and the *BidderConfigurationProperties
        # suffix belongs to two framework classes. The subclass is now emitted
        # nested by configuration.java.j2.
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
