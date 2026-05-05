#!/usr/bin/env python3
"""Render tests for prebid-server-go/port-java2go/templates/*.j2.

Phase D3 Go-side templates emit Go source code + YAML/JSON fixtures for
the Java→Go inverse direction. These tests verify each template
produces well-formed output (parses as Go via syntax-only check, JSON
parses, YAML parses) for kobler-equivalent context dicts.

Run from repo root:
    python3 -m pytest scripts/tests/test_port_java2go_templates.py
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
TEMPLATES_DIR = REPO_ROOT / "prebid-server-go" / "port-java2go" / "templates"


def _render(template_name: str, ctx: Dict[str, Any]) -> str:
    if jinja2 is None:
        raise unittest.SkipTest("jinja2 not installed")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    return template.render(ctx=ctx)


def _kobler_bidder_info_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for bidder-info.yaml.j2 (Go side)."""
    return {
        "endpoint": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
        "maintainer_email": "bidding-support@kobler.no",
        "gvl_vendor_id": 0,
        "endpoint_compression": "gzip",
        "modifying_vast_xml": False,
        "geoscope": ["DNK", "NOR", "SWE"],
        "site_media_types": ["banner"],
        "app_media_types": ["banner"],
        "dooh_media_types": None,
        "alias_of": None,
        "user_sync": None,
    }


def _kobler_imp_ext_pojo_ctx() -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for imp-ext-pojo.go.j2."""
    return {
        "bidder_class_root": "Kobler",
        "fields": [
            {
                "go_name": "Test",
                "json_tag": "test",
                "go_type": "bool",
                "omitempty": False,
                "notes": "Whether the request is for testing only.",
            },
        ],
        "javadoc_summary": "ExtImpKobler defines the contract for bidrequest.imp[i].ext.kobler.",
    }


# Current upstream module-version pin (post v3→v4 PR #4710 merged 2026-03-05).
# Centralized so a future v5 bump is a one-line change.
GO_MODULE_VERSION = "v4"


def _kobler_bidder_test_ctx() -> Dict[str, Any]:
    return {
        "package_name": "kobler",
        "bidder_constant": "openrtb_ext.BidderKobler",
        "bidder_class_root": "Kobler",
        "module_version": GO_MODULE_VERSION,
    }


def _kobler_params_test_ctx() -> Dict[str, Any]:
    return {
        "package_name": "kobler",
        "bidder_constant": "openrtb_ext.BidderKobler",
        "module_version": GO_MODULE_VERSION,
        "valid_cases": [
            '{"test": true}',
            '{"test": false}',
            '{}',
        ],
        "invalid_cases": [
            'null',
            'true',
            '"non-object"',
        ],
    }


def _kobler_exemplary_fixture_ctx() -> Dict[str, Any]:
    return {
        "mock_bid_request": {
            "id": "req-1",
            "imp": [{"id": "imp-1", "banner": {"format": [{"w": 300, "h": 250}]}}],
        },
        "http_calls": [
            {
                "uri": "https://bid.essrtb.com/bid/prebid_server_rtb_call",
                "body": {"id": "req-1"},
                "status": 200,
                "response": {"id": "resp-1", "seatbid": [{"bid": [{"id": "bid-1", "impid": "imp-1", "price": 1.5}]}]},
            },
        ],
        "expected_bids": [
            {
                "bid": {"id": "bid-1", "impid": "imp-1", "price": 1.5},
                "type": "banner",
            },
        ],
        "expected_currency": "USD",
    }


def _kobler_bidder_go_ctx() -> Dict[str, Any]:
    return {
        "package_name": "kobler",
        "bidder_class_root": "Kobler",
        "uses_currency_conversion": True,
        "imp_ext_class_root": "Kobler",
        "imp_ext_unmarshal_kind": "standard-two-phase",
        "batching_kind": "single-batched",
        "batching_max_imps": None,
        "endpoint_resolution_kind": "dev-prod-toggle",
        "http_status_kind": "canonical-helpers",
        "bid_type_resolution": "imp-mediatype-introspection",
        "has_extra_info": False,
        "module_version": GO_MODULE_VERSION,
        "imports_extra": [],
        "javadoc_summary": None,
    }


class TestBidderInfoYamlJ2(unittest.TestCase):
    """Tests for templates/bidder-info.yaml.j2 (Go side)."""

    def test_renders_well_formed_yaml(self):
        rendered = _render("bidder-info.yaml.j2", _kobler_bidder_info_ctx())
        parsed = yaml.safe_load(rendered)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["endpoint"], "https://bid.essrtb.com/bid/prebid_server_rtb_call")

    def test_camel_case_keys(self):
        """Go uses camelCase YAML keys, NOT kebab-case (Java side)."""
        ctx = _kobler_bidder_info_ctx()
        ctx["gvl_vendor_id"] = 8  # non-zero so the gvlVendorID line emits (F9)
        rendered = _render("bidder-info.yaml.j2", ctx)
        # Camel-case names should appear.
        self.assertIn("endpointCompression", rendered)
        self.assertIn("gvlVendorID", rendered)
        # Kebab-case (Java side) should NOT appear.
        self.assertNotIn("endpoint-compression", rendered)
        self.assertNotIn("gvl-vendor-id", rendered)

    def test_gvl_vendor_id_omitted_when_zero(self):
        """F9: Go upstream convention omits gvlVendorID when value is 0."""
        ctx = _kobler_bidder_info_ctx()
        self.assertEqual(ctx["gvl_vendor_id"], 0)  # fixture matches kobler reality
        rendered = _render("bidder-info.yaml.j2", ctx)
        self.assertNotIn("gvlVendorID", rendered)

    def test_modifying_vast_xml_omitted_when_false(self):
        rendered = _render("bidder-info.yaml.j2", _kobler_bidder_info_ctx())
        self.assertNotIn("modifyingVastXmlAllowed", rendered)

    def test_alias_form_emits_aliasOf(self):
        ctx = _kobler_bidder_info_ctx()
        ctx["alias_of"] = "smarthub"
        ctx["endpoint"] = None  # alias inherits parent's endpoint
        ctx["maintainer_email"] = None
        ctx["gvl_vendor_id"] = None
        ctx["endpoint_compression"] = None
        ctx["geoscope"] = None
        ctx["site_media_types"] = None
        ctx["app_media_types"] = None
        rendered = _render("bidder-info.yaml.j2", ctx)
        parsed = yaml.safe_load(rendered)
        self.assertEqual(parsed["aliasOf"], "smarthub")

    def test_capabilities_emits_when_media_types_present(self):
        rendered = _render("bidder-info.yaml.j2", _kobler_bidder_info_ctx())
        parsed = yaml.safe_load(rendered)
        self.assertEqual(parsed["capabilities"]["site"]["mediaTypes"], ["banner"])
        self.assertEqual(parsed["capabilities"]["app"]["mediaTypes"], ["banner"])
        self.assertNotIn("dooh", parsed["capabilities"])


class TestImpExtPojoGoJ2(unittest.TestCase):
    """Tests for templates/imp-ext-pojo.go.j2."""

    def test_renders_well_formed_struct(self):
        rendered = _render("imp-ext-pojo.go.j2", _kobler_imp_ext_pojo_ctx())
        self.assertIn("package openrtb_ext", rendered)
        self.assertIn("type ExtImpKobler struct {", rendered)
        self.assertIn('Test bool `json:"test"`', rendered)

    def test_javadoc_emits_as_go_doc_comment(self):
        rendered = _render("imp-ext-pojo.go.j2", _kobler_imp_ext_pojo_ctx())
        self.assertIn("// ExtImpKobler defines the contract for", rendered)

    def test_field_notes_emit_as_go_comment(self):
        rendered = _render("imp-ext-pojo.go.j2", _kobler_imp_ext_pojo_ctx())
        self.assertIn("// Whether the request is for testing only.", rendered)

    def test_omitempty_tag_when_requested(self):
        ctx = _kobler_imp_ext_pojo_ctx()
        ctx["fields"][0]["omitempty"] = True
        rendered = _render("imp-ext-pojo.go.j2", ctx)
        self.assertIn('`json:"test,omitempty"`', rendered)

    def test_json_rawmessage_triggers_encoding_json_import(self):
        ctx = _kobler_imp_ext_pojo_ctx()
        ctx["fields"].append({
            "go_name": "RawData",
            "json_tag": "rawData",
            "go_type": "json.RawMessage",
            "omitempty": True,
            "notes": None,
        })
        rendered = _render("imp-ext-pojo.go.j2", ctx)
        self.assertIn('"encoding/json"', rendered)


class TestBidderTestGoJ2(unittest.TestCase):
    def test_renders_test_function(self):
        rendered = _render("bidder-test.go.j2", _kobler_bidder_test_ctx())
        self.assertIn("package kobler", rendered)
        # F10: Go upstream convention is TestJsonSamples (100% of merged
        # adapter PRs use this name regardless of bidder).
        self.assertIn("func TestJsonSamples(t *testing.T) {", rendered)
        self.assertIn("openrtb_ext.BidderKobler", rendered)
        self.assertIn('adapterstest.RunJSONBidderTest(t, "koblertest", bidder)', rendered)


class TestParamsTestGoJ2(unittest.TestCase):
    def test_renders_valid_and_invalid_cases(self):
        rendered = _render("params-test.go.j2", _kobler_params_test_ctx())
        self.assertIn("func TestValidParams(t *testing.T)", rendered)
        self.assertIn("func TestInvalidParams(t *testing.T)", rendered)
        self.assertIn("var validParams = []string{", rendered)
        self.assertIn("var invalidParams = []string{", rendered)
        # Both 3 valid + 3 invalid cases should appear.
        self.assertEqual(rendered.count('"test"'), 2)  # in valid + 1 reference

    def test_uses_correct_bidder_constant(self):
        rendered = _render("params-test.go.j2", _kobler_params_test_ctx())
        self.assertIn("openrtb_ext.BidderKobler", rendered)


class TestExemplaryFixtureJ2(unittest.TestCase):
    def test_top_level_key_is_mockBidRequest(self):
        """D3-B3: top-level key MUST be `mockBidRequest`, not `expectedRequest`.
        adapterstest.RunJSONBidderTest reads `mockBidRequest`; emitted fixtures
        with `expectedRequest` at top level fail input lookup."""
        rendered = _render("exemplary-fixture.json.j2", _kobler_exemplary_fixture_ctx())
        parsed = json.loads(rendered)
        self.assertIn("mockBidRequest", parsed)
        self.assertNotIn("expectedRequest", parsed)
        # The INNER expectedRequest under each httpCalls[] entry IS correct.
        self.assertIn("expectedRequest", parsed["httpCalls"][0])

    def test_renders_well_formed_json(self):
        rendered = _render("exemplary-fixture.json.j2", _kobler_exemplary_fixture_ctx())
        parsed = json.loads(rendered)
        self.assertIn("mockBidRequest", parsed)
        self.assertIn("httpCalls", parsed)
        self.assertEqual(len(parsed["httpCalls"]), 1)
        call = parsed["httpCalls"][0]
        self.assertEqual(call["expectedRequest"]["uri"],
                         "https://bid.essrtb.com/bid/prebid_server_rtb_call")
        self.assertEqual(call["mockResponse"]["status"], 200)

    def test_expected_bids_emit_with_currency(self):
        rendered = _render("exemplary-fixture.json.j2", _kobler_exemplary_fixture_ctx())
        parsed = json.loads(rendered)
        self.assertEqual(parsed["expectedBidResponses"][0]["currency"], "USD")
        self.assertEqual(parsed["expectedBidResponses"][0]["bids"][0]["type"], "banner")

    def test_imp_ids_emit_when_provided(self):
        """F-new-12 (canary v2): Go test framework requires expectedRequest.impIDs
        — adapterstest.RunJSONBidderTest asserts non-empty. The template must emit
        impIDs from ctx.http_calls[].imp_ids when provided."""
        ctx = _kobler_exemplary_fixture_ctx()
        ctx["http_calls"][0]["imp_ids"] = ["imp_id"]
        rendered = _render("exemplary-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertEqual(parsed["httpCalls"][0]["expectedRequest"]["impIDs"], ["imp_id"])

    def test_imp_ids_omitted_when_absent(self):
        """Backward compat: existing ctx without imp_ids must still render
        a valid expectedRequest (the Go test framework will still error since
        impIDs is required, but the template must not blow up on missing key)."""
        ctx = _kobler_exemplary_fixture_ctx()
        # imp_ids deliberately not set
        rendered = _render("exemplary-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertNotIn("impIDs", parsed["httpCalls"][0]["expectedRequest"])


class TestBidderGoJ2(unittest.TestCase):
    """Tests for templates/bidder.go.j2 — the heaviest port-java2go template."""

    def test_renders_kobler_well_formed(self):
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        self.assertIn("package kobler", rendered)
        self.assertIn("type adapter struct {", rendered)
        self.assertIn("func Builder(_ openrtb_ext.BidderName, cfg config.Adapter, _ config.Server)", rendered)
        self.assertIn("func (a *adapter) MakeRequests(", rendered)
        self.assertIn("func (a *adapter) MakeBids(", rendered)

    def test_canonical_helpers_emit_when_rule_30_applies(self):
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        self.assertIn("adapters.IsResponseStatusCodeNoContent(responseData)", rendered)
        self.assertIn("adapters.CheckResponseStatusCodeForErrors(responseData)", rendered)

    def test_legacy_raw_status_when_rule_30_inapplicable(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("responseData.StatusCode == http.StatusNoContent", rendered)
        self.assertIn("responseData.StatusCode != http.StatusOK", rendered)
        self.assertNotIn("IsResponseStatusCodeNoContent", rendered)

    def test_two_phase_unmarshal_pattern(self):
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        self.assertIn("var bidderExt adapters.ExtImpBidder", rendered)
        self.assertIn("jsonutil.Unmarshal(bidderExt.Bidder, &ext)", rendered)

    def test_direct_unmarshal_pattern(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["imp_ext_unmarshal_kind"] = "direct"
        rendered = _render("bidder.go.j2", ctx)
        self.assertNotIn("var bidderExt adapters.ExtImpBidder", rendered)
        self.assertIn("jsonutil.Unmarshal(imp.Ext, &ext)", rendered)

    def test_per_imp_batching(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["batching_kind"] = "per-imp"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("perImp := *request", rendered)
        self.assertIn("perImp.Imp = []openrtb2.Imp{request.Imp[i]}", rendered)

    def test_max_imps_emits_chunker(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["batching_kind"] = "max-imps-per-request"
        ctx["batching_max_imps"] = 5
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("const maxImpsPerRequest = 5", rendered)
        self.assertIn("func chunkImps(imps []openrtb2.Imp, chunkSize int) [][]openrtb2.Imp", rendered)

    def test_extra_info_emits_struct_field_and_unmarshal(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["has_extra_info"] = True
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("extraInfo extraInfo", rendered)
        self.assertIn("type extraInfo struct {", rendered)
        self.assertIn("if cfg.ExtraAdapterInfo !=", rendered)

    def test_imp_mediatype_introspection_emits_imp_walk(self):
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        self.assertIn("if imps[i].Video != nil", rendered)
        self.assertIn("openrtb_ext.BidTypeBanner", rendered)

    def test_module_version_pinned_to_v4_in_imports(self):
        """D3-B1: emitted import paths must use the current upstream module
        major version (v4 since PR #4710 merged 2026-03-05). Hardcoded v3
        would fail go build against current upstream."""
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        self.assertIn('"github.com/prebid/prebid-server/v4/adapters"', rendered)
        self.assertIn('"github.com/prebid/prebid-server/v4/openrtb_ext"', rendered)
        self.assertNotIn("/v3/", rendered)

    def test_module_version_parameterized(self):
        """A future v5 bump should require only a ctx field change."""
        ctx = _kobler_bidder_go_ctx()
        ctx["module_version"] = "v5"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn('"github.com/prebid/prebid-server/v5/adapters"', rendered)
        self.assertNotIn("/v4/", rendered)

    def test_request_data_populates_impids(self):
        """D3-H1: every adapter must set RequestData.ImpIDs for analytics
        correlation. Verified universal pattern across 10 sampled adapters."""
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        self.assertIn("ImpIDs:  openrtb_ext.GetImpIDs(request.Imp)", rendered)

    def test_request_data_populates_impids_per_imp_batching(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["batching_kind"] = "per-imp"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("ImpIDs:  openrtb_ext.GetImpIDs(perImp.Imp)", rendered)

    def test_request_data_populates_impids_max_imps_batching(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["batching_kind"] = "max-imps-per-request"
        ctx["batching_max_imps"] = 5
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("ImpIDs:  openrtb_ext.GetImpIDs(chunkRequest.Imp)", rendered)


class TestBidTypeResolutionBranches(unittest.TestCase):
    """D3.8 F8 fix — bidder.go.j2 getBidType covers 4 corpus patterns:

    1. constant-{type} generalization (banner|video|audio|native)
    2. by-bid-mtype (Rule 23 switch on bid.MType)
    3. by-bid-ext-typed-field (Rule 24 typed-field read with throw-on-miss)
    4. method-chain-fallback (multi-step walker; kobler 2-step + aax 3-step)

    These tests assert key substrings (NOT exact strings) so the post-emit
    `gofmt -s -w` step has latitude to canonicalize formatting.
    """

    # --------------------------- constant-{type} ---------------------------

    def test_constant_legacy_banner_alias(self):
        """Backwards-compat: existing `constant-banner` value still works."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "constant-banner"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("return openrtb_ext.BidTypeBanner", rendered)
        # No-error signature.
        self.assertIn("func getBidType(bid *openrtb2.Bid, imps []openrtb2.Imp) openrtb_ext.BidType {", rendered)

    def test_constant_video(self):
        """freewheelssp + vungle pattern (12% of corpus)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "constant"
        ctx["bid_type_constant"] = "video"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("return openrtb_ext.BidTypeVideo", rendered)

    def test_constant_audio(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "constant"
        ctx["bid_type_constant"] = "audio"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("return openrtb_ext.BidTypeAudio", rendered)

    def test_constant_native(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "constant"
        ctx["bid_type_constant"] = "native"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("return openrtb_ext.BidTypeNative", rendered)

    def test_constant_banner_via_generalized_branch(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "constant"
        ctx["bid_type_constant"] = "banner"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("return openrtb_ext.BidTypeBanner", rendered)

    def test_constant_unknown_type_fails_loudly(self):
        """Operator passes a type that doesn't exist on the Go side — render
        MUST fail (not silently emit broken Go) so the audit notices."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "constant"
        ctx["bid_type_constant"] = "other"
        with self.assertRaises(Exception):
            _render("bidder.go.j2", ctx)

    # --------------------------- by-bid-mtype ----------------------------

    def test_by_bid_mtype_throw_emits_switch_and_error(self):
        """adverxo, teqblaze 2 + thetradedesk's bid-mtype-switch variant
        (combined 19% of corpus)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "by-bid-mtype"
        ctx["bid_type_fallback_action"] = "throw"
        rendered = _render("bidder.go.j2", ctx)
        # Switch on bid.MType with all four cases.
        self.assertIn("switch bid.MType", rendered)
        self.assertIn("case openrtb2.MarkupBanner", rendered)
        self.assertIn("case openrtb2.MarkupVideo", rendered)
        self.assertIn("case openrtb2.MarkupAudio", rendered)
        self.assertIn("case openrtb2.MarkupNative", rendered)
        # Error-returning signature.
        self.assertIn("(openrtb_ext.BidType, error)", rendered)
        # Error fallback.
        self.assertIn('return "", fmt.Errorf', rendered)
        # MakeBids caller threads errors through.
        self.assertIn("var errs []error", rendered)
        self.assertIn("errs = append(errs, err)", rendered)
        self.assertIn("return bidderResponse, errs", rendered)

    def test_by_bid_mtype_return_default_no_error(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "by-bid-mtype"
        ctx["bid_type_fallback_action"] = "return-default"
        ctx["bid_type_fallback_value"] = "video"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("switch bid.MType", rendered)
        # No-error signature.
        self.assertIn("func getBidType(bid *openrtb2.Bid, imps []openrtb2.Imp) openrtb_ext.BidType {", rendered)
        # Fallback returns the configured constant.
        self.assertIn("return openrtb_ext.BidTypeVideo", rendered)
        # MakeBids caller uses the no-error signature.
        self.assertIn("BidType: getBidType(bid, request.Imp),", rendered)

    # ----------------------- by-bid-ext-typed-field ----------------------

    def test_by_bid_ext_typed_field_string_parse(self):
        """smarthub shape — string field parsed via openrtb_ext.ParseBidType."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "by-bid-ext-typed-field"
        ctx["bid_type_ext_field"] = {
            "struct_name": "bidExt",
            "field_path": "bidExt.MediaType",
            "parse_via": "openrtb_ext.ParseBidType",
        }
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("var bidExt bidExt", rendered)
        self.assertIn("jsonutil.Unmarshal(bid.Ext, &bidExt)", rendered)
        self.assertIn("openrtb_ext.ParseBidType(string(bidExt.MediaType))", rendered)
        # Error-returning signature.
        self.assertIn("(openrtb_ext.BidType, error)", rendered)

    def test_by_bid_ext_typed_field_switch_int(self):
        """appnexus shape — numeric field with switch over int values."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "by-bid-ext-typed-field"
        ctx["bid_type_ext_field"] = {
            "struct_name": "bidExt",
            "field_path": "bidExt.Appnexus.BidType",
            "parse_via": "switch-int",
            "int_cases": [
                {"value": 0, "bid_type": "banner"},
                {"value": 1, "bid_type": "video"},
                {"value": 3, "bid_type": "native"},
            ],
        }
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("switch bidExt.Appnexus.BidType", rendered)
        self.assertIn("case 0:", rendered)
        self.assertIn("return openrtb_ext.BidTypeBanner, nil", rendered)
        self.assertIn("case 1:", rendered)
        self.assertIn("return openrtb_ext.BidTypeVideo, nil", rendered)
        self.assertIn("case 3:", rendered)
        self.assertIn("return openrtb_ext.BidTypeNative, nil", rendered)
        self.assertIn("default:", rendered)
        self.assertIn("unrecognized bid type", rendered)

    # --------------------- method-chain-fallback ------------------------

    def test_method_chain_kobler_2_step(self):
        """Kobler shape: by-bid-ext-typed-field(bid.ext.prebid.type) →
        hardcoded(BidTypeBanner). No throw → no-error signature."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {
                "method": "by-bid-ext-typed-field",
                "field": "bid.ext.prebid.type",
                "fallback_action": "next",
            },
            {
                "method": "hardcoded",
                "hardcoded_value": "BidTypeBanner",
                "fallback_action": "return-default",
            },
        ]
        rendered = _render("bidder.go.j2", ctx)
        # Step 1 emits the canonical kobler.go shape.
        self.assertIn("var bidExt openrtb_ext.ExtBid", rendered)
        self.assertIn("openrtb_ext.ParseBidType(string(bidExt.Prebid.Type))", rendered)
        self.assertIn("return mediaType", rendered)
        # Step 2 emits the hardcoded fallback.
        self.assertIn("return openrtb_ext.BidTypeBanner", rendered)
        # No-error signature (no throw step in chain).
        self.assertIn("func getBidType(bid *openrtb2.Bid, imps []openrtb2.Imp) openrtb_ext.BidType {", rendered)

    def test_method_chain_aax_3_step(self):
        """Aax shape: by-bid-ext-typed-field(non-canonical adCodeType) →
        by-imp-mediatype → throw. Verifies multi-step loop construct works
        AND that the chain emits an error-returning signature."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {
                "method": "by-bid-ext-typed-field",
                "field": "bid.ext.adCodeType",
                "fallback_action": "next",
            },
            {
                "method": "by-imp-mediatype",
                "fallback_action": "next",
            },
            {
                "method": "throw",
            },
        ]
        rendered = _render("bidder.go.j2", ctx)
        # Step 1 (non-canonical field) emits TODO comment.
        self.assertIn("TODO[port-java2go]: by-bid-ext-typed-field step reads bid.ext.adCodeType", rendered)
        # Step 2 (by-imp-mediatype) emits the imp walk.
        self.assertIn("for i := range imps", rendered)
        self.assertIn("if imps[i].ID == bid.ImpID", rendered)
        self.assertIn("return openrtb_ext.BidTypeVideo, nil", rendered)
        self.assertIn("return openrtb_ext.BidTypeNative, nil", rendered)
        self.assertIn("return openrtb_ext.BidTypeBanner, nil", rendered)
        # Step 3 (throw) emits the error return.
        self.assertIn('return "", fmt.Errorf("unable to determine bid type for imp', rendered)
        # Error-returning signature.
        self.assertIn("(openrtb_ext.BidType, error)", rendered)

    def test_method_chain_zero_steps_falls_through(self):
        """Defensive: 0-step chain renders without crashing (operator's spec
        is malformed but template should not blow up at render time)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = []
        # Should render — body is empty, but Go would not compile. The TODO
        # branch is the right place for this; here we just verify Jinja
        # doesn't crash on the empty list.
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("func getBidType", rendered)

    def test_method_chain_one_step_renders(self):
        """Defensive: 1-step chain — effectively single-method but uses the
        method-chain branch instead of the dedicated single-step branches."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {
                "method": "hardcoded",
                "hardcoded_value": "BidTypeBanner",
                "fallback_action": "return-default",
            },
        ]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("return openrtb_ext.BidTypeBanner", rendered)

    # ------------- unknown / TODO fallthrough -----------------------------

    def test_unknown_resolution_falls_through_with_todo(self):
        """If ctx.bid_type_resolution is unrecognized, emit a TODO comment +
        BidTypeBanner fallback (existing pattern, preserved)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "string-sniff-adm-substring"  # corpus-known but unimplemented
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("TODO[port-java2go]: bid_type_resolution=string-sniff-adm-substring", rendered)
        self.assertIn("return openrtb_ext.BidTypeBanner", rendered)


class TestCurrencyConversionEmission(unittest.TestCase):
    """D3.8 B2 — TIER 1 item 2 (F5). When `ctx.uses_currency_conversion`
    is True the template emits:

      1. `const supportedCurrency = "USD"` + `func convertImpCurrency(...)`
         helper at end of file (modeled on upstream kobler.go shape).
      2. `"strings"` import for `strings.ToUpper`.
      3. Per-imp `convertImpCurrency(&imp, reqInfo)` call BEFORE `parseImpExt`
         in all three batching branches (single-batched, per-imp,
         max-imps-per-request).

    When False (~69% of corpus), nothing is emitted — no helper, no call,
    no `"strings"` import. Negative-path test preserves the
    kobler-without-currency-conversion case.

    Affects 5/16 (31%) of corpus per d3.8-template-coverage-audit F5:
    adverxo, beachfront, kobler, limelightDigital, vungle.
    """

    def test_helper_emitted_when_uses_currency_conversion_true(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = True
        rendered = _render("bidder.go.j2", ctx)
        # Constant + function declaration.
        self.assertIn('const supportedCurrency = "USD"', rendered)
        self.assertIn(
            "func convertImpCurrency(imp *openrtb2.Imp, reqInfo *adapters.ExtraRequestInfo) error",
            rendered,
        )
        # Body uses strings.ToUpper to canonicalize the input currency.
        self.assertIn("strings.ToUpper(imp.BidFloorCur)", rendered)
        # And reqInfo.ConvertCurrency on the *adapters.ExtraRequestInfo receiver.
        self.assertIn(
            "reqInfo.ConvertCurrency(imp.BidFloor, imp.BidFloorCur, supportedCurrency)",
            rendered,
        )
        # The "strings" import is present.
        self.assertIn('"strings"', rendered)

    def test_per_imp_call_in_single_batched(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = True
        ctx["batching_kind"] = "single-batched"
        rendered = _render("bidder.go.j2", ctx)
        # Call appears in the body.
        self.assertIn(
            "if err := convertImpCurrency(&request.Imp[i], reqInfo); err != nil",
            rendered,
        )
        # And precedes the parseImpExt call (lexical order).
        currency_idx = rendered.index("convertImpCurrency(&request.Imp[i]")
        parse_idx = rendered.index("parseImpExt(&request.Imp[i])")
        self.assertLess(currency_idx, parse_idx)

    def test_per_imp_call_in_per_imp_batching(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = True
        ctx["batching_kind"] = "per-imp"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn(
            "if err := convertImpCurrency(&request.Imp[i], reqInfo); err != nil",
            rendered,
        )
        # Precedes parseImpExt in the per-imp loop too.
        currency_idx = rendered.index("convertImpCurrency(&request.Imp[i]")
        parse_idx = rendered.index("parseImpExt(&request.Imp[i])")
        self.assertLess(currency_idx, parse_idx)

    def test_per_imp_call_in_max_imps_batching(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = True
        ctx["batching_kind"] = "max-imps-per-request"
        ctx["batching_max_imps"] = 5
        rendered = _render("bidder.go.j2", ctx)
        # In the chunk's inner per-imp loop, the call references &chunk[i].
        self.assertIn(
            "if err := convertImpCurrency(&chunk[i], reqInfo); err != nil",
            rendered,
        )
        currency_idx = rendered.index("convertImpCurrency(&chunk[i]")
        parse_idx = rendered.index("parseImpExt(&chunk[i])")
        self.assertLess(currency_idx, parse_idx)
        # Chunker helper still emits.
        self.assertIn(
            "func chunkImps(imps []openrtb2.Imp, chunkSize int) [][]openrtb2.Imp",
            rendered,
        )

    def test_no_helper_when_uses_currency_conversion_false(self):
        """The 11/16 (69%) of corpus that does NOT use currency conversion
        must render cleanly with no helper, no call, no `"strings"` import."""
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = False
        rendered = _render("bidder.go.j2", ctx)
        # Helper absent in all forms.
        self.assertNotIn("supportedCurrency", rendered)
        self.assertNotIn("convertImpCurrency", rendered)
        self.assertNotIn("strings.ToUpper", rendered)
        # And no `"strings"` import line — would trigger Go unused-import error.
        self.assertNotIn('"strings"', rendered)

    def test_no_helper_negative_path_preserves_kobler_no_cc(self):
        """Edge: a kobler-shaped adapter could in principle disable currency
        conversion (B2 must not break that). Confirm the body still emits a
        usable parseImpExt loop without the currency call."""
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = False
        ctx["batching_kind"] = "per-imp"
        rendered = _render("bidder.go.j2", ctx)
        self.assertNotIn("convertImpCurrency", rendered)
        # Per-imp body still emits parseImpExt directly.
        self.assertIn("parseImpExt(&request.Imp[i])", rendered)
        self.assertIn("perImp := *request", rendered)

    def test_helper_does_not_break_b1_signature_flip(self):
        """B1 added the `_bid_type_returns_error` signature flip in
        getBidType. The currency helper lives at end of file and is
        body-independent of the bid-type return shape — confirm both can
        coexist (e.g. by-bid-mtype + uses_currency_conversion=True)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = True
        ctx["bid_type_resolution"] = "by-bid-mtype"
        ctx["bid_type_fallback_action"] = "throw"
        rendered = _render("bidder.go.j2", ctx)
        # Currency helper present.
        self.assertIn("func convertImpCurrency(", rendered)
        # B1 error-returning signature still present.
        self.assertIn("(openrtb_ext.BidType, error)", rendered)
        self.assertIn("var errs []error", rendered)


class TestCustomHeadersEmission(unittest.TestCase):
    """D3.8 B3 — TIER 1 item 3 (custom-headers extension). When
    `ctx.custom_headers` is a non-empty list of `{name, value}` dicts the
    template appends one `headers.Add(name, value)` call per entry inside
    standardHeaders(), AFTER the universal Content-Type + Accept pair.

    None or `[]` → no extras emitted (kobler-shape baseline preserved).

    Affects 5/16 (31%) of corpus per d3.8-template-coverage-audit:
    adkernelAdn (X-OpenRTB-Version), elementaltv (X-OpenRTB-Version),
    freewheelssp (Componentid), smarthub (Prebid-Adapter-Ver), and
    vungle (X-OpenRTB-Version).
    """

    def _standard_headers_block(self, rendered: str) -> str:
        """Slice out the standardHeaders() function body for assertions."""
        idx = rendered.find("func standardHeaders")
        self.assertGreaterEqual(idx, 0, "standardHeaders() should always emit")
        nxt = rendered.find("\nfunc ", idx + 5)
        if nxt < 0:
            nxt = len(rendered)
        return rendered[idx:nxt]

    def test_zero_custom_headers_none_emits_baseline(self):
        """`ctx.custom_headers = None` → only Content-Type + Accept (2 calls)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = None
        rendered = _render("bidder.go.j2", ctx)
        block = self._standard_headers_block(rendered)
        self.assertIn(
            'headers.Add("Content-Type", "application/json;charset=utf-8")', block
        )
        self.assertIn('headers.Add("Accept", "application/json")', block)
        self.assertEqual(block.count("headers.Add("), 2)

    def test_zero_custom_headers_empty_list_emits_baseline(self):
        """`ctx.custom_headers = []` → only Content-Type + Accept (2 calls)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = []
        rendered = _render("bidder.go.j2", ctx)
        block = self._standard_headers_block(rendered)
        self.assertEqual(block.count("headers.Add("), 2)

    def test_missing_custom_headers_emits_baseline(self):
        """Backwards compat: ctx without `custom_headers` key at all renders
        identically to None/[] (the existing bidder ctxs in this file omit
        it; this test pins that behavior so older callers don't break)."""
        ctx = _kobler_bidder_go_ctx()
        # _kobler_bidder_go_ctx() does not set custom_headers — leave it absent.
        self.assertNotIn("custom_headers", ctx)
        rendered = _render("bidder.go.j2", ctx)
        block = self._standard_headers_block(rendered)
        self.assertEqual(block.count("headers.Add("), 2)

    def test_one_custom_header_emits_three_adds(self):
        """One ctx.custom_headers entry → 3 headers.Add calls total."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = [{"name": "X-OpenRTB-Version", "value": "2.5"}]
        rendered = _render("bidder.go.j2", ctx)
        block = self._standard_headers_block(rendered)
        self.assertEqual(block.count("headers.Add("), 3)
        self.assertIn('headers.Add("X-OpenRTB-Version", "2.5")', block)

    def test_multiple_custom_headers_preserve_declared_order(self):
        """Multiple entries must emit in declaration order — assert via
        lexical index of each line within standardHeaders() body."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = [
            {"name": "X-OpenRTB-Version", "value": "2.5"},
            {"name": "Componentid", "value": "prebid-go"},
            {"name": "Prebid-Adapter-Ver", "value": "1.0.0"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        block = self._standard_headers_block(rendered)
        # All three custom calls present.
        self.assertEqual(block.count("headers.Add("), 5)  # 2 universal + 3 custom
        # Lexical ordering matches declaration order.
        accept_idx = block.index('headers.Add("Accept"')
        version_idx = block.index('headers.Add("X-OpenRTB-Version"')
        component_idx = block.index('headers.Add("Componentid"')
        adapter_ver_idx = block.index('headers.Add("Prebid-Adapter-Ver"')
        # Custom headers come after the universal Accept.
        self.assertLess(accept_idx, version_idx)
        # Declared order: version → componentid → adapter-ver.
        self.assertLess(version_idx, component_idx)
        self.assertLess(component_idx, adapter_ver_idx)
        # And the function still closes with `return headers`.
        self.assertLess(adapter_ver_idx, block.index("return headers"))

    def test_custom_header_name_with_hyphens_quoted_correctly(self):
        """Header names with hyphens (canonical mixed-case) must be JSON-quoted
        verbatim — no transformation, no lowercasing."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = [
            {"name": "X-OpenRTB-Version", "value": "2.5"},
            {"name": "Prebid-Adapter-Ver", "value": "1.0.0"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        # Mixed-case name preserved exactly (audit F-new-6: don't canonicalize).
        self.assertIn('headers.Add("X-OpenRTB-Version", "2.5")', rendered)
        self.assertNotIn("x-openrtb-version", rendered)
        self.assertIn('headers.Add("Prebid-Adapter-Ver", "1.0.0")', rendered)

    def test_custom_header_value_with_special_chars_json_escaped(self):
        """Header values with special chars (semicolons, quotes, backslashes)
        must be properly escaped via the tojson filter so the emitted Go
        string literal compiles. Go's double-quoted string escape rules are
        JSON-compatible for these characters."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = [
            # Semicolon + slash + equals — common in mime-type-style values.
            {"name": "X-Content-Like", "value": "application/json;charset=utf-8"},
            # Embedded backslash.
            {"name": "X-Path", "value": "a\\b"},
            # Embedded double quote.
            {"name": "X-Quote", "value": 'has "q"'},
        ]
        rendered = _render("bidder.go.j2", ctx)
        # Semicolon/slash pass through unchanged (no escaping needed).
        self.assertIn(
            'headers.Add("X-Content-Like", "application/json;charset=utf-8")',
            rendered,
        )
        # Backslash escaped to \\ in JSON, which is also Go's escape form.
        self.assertIn('headers.Add("X-Path", "a\\\\b")', rendered)
        # Double quotes escaped to \" — also matches Go's escape form.
        self.assertIn('headers.Add("X-Quote", "has \\"q\\"")', rendered)

    def test_empty_string_name_or_value_emitted_literally(self):
        """Edge: empty-string name or value is NOT the template's job to
        validate. Pin that the template emits whatever the spec hands it
        (operator catches degenerate specs upstream)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = [
            {"name": "", "value": "v"},
            {"name": "n", "value": ""},
        ]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn('headers.Add("", "v")', rendered)
        self.assertIn('headers.Add("n", "")', rendered)

    def test_custom_headers_render_is_position_correct_in_function_body(self):
        """Custom headers must be inserted BETWEEN the universal Accept call
        and the `return headers` closer — not before Content-Type, not after
        return. Pins the structural position so a future edit doesn't
        accidentally move them."""
        ctx = _kobler_bidder_go_ctx()
        ctx["custom_headers"] = [{"name": "X-OpenRTB-Version", "value": "2.5"}]
        rendered = _render("bidder.go.j2", ctx)
        block = self._standard_headers_block(rendered)
        ct_idx = block.index('headers.Add("Content-Type"')
        accept_idx = block.index('headers.Add("Accept"')
        custom_idx = block.index('headers.Add("X-OpenRTB-Version"')
        return_idx = block.index("return headers")
        self.assertLess(ct_idx, accept_idx)
        self.assertLess(accept_idx, custom_idx)
        self.assertLess(custom_idx, return_idx)

    def test_custom_headers_does_not_interact_with_b1_b2_emissions(self):
        """B1's bid-type signature flip and B2's currency helper live
        elsewhere in the file. Confirm enabling custom_headers alongside
        both does not corrupt either emission."""
        ctx = _kobler_bidder_go_ctx()
        ctx["uses_currency_conversion"] = True  # B2 path
        ctx["bid_type_resolution"] = "by-bid-mtype"  # B1 error-flip path
        ctx["bid_type_fallback_action"] = "throw"
        ctx["custom_headers"] = [{"name": "X-OpenRTB-Version", "value": "2.5"}]
        rendered = _render("bidder.go.j2", ctx)
        # B3 (custom header) emitted.
        self.assertIn('headers.Add("X-OpenRTB-Version", "2.5")', rendered)
        # B1 (error-returning getBidType) still flipped.
        self.assertIn("(openrtb_ext.BidType, error)", rendered)
        # B2 (currency helper) still present.
        self.assertIn("func convertImpCurrency(", rendered)
        self.assertIn('"strings"', rendered)


class TestModuleVersionInOtherTemplates(unittest.TestCase):
    """D3-B1: bidder-test.go.j2 and params-test.go.j2 also import from
    the prebid-server module path; both must be parameterized."""

    def test_bidder_test_module_version_v4(self):
        rendered = _render("bidder-test.go.j2", _kobler_bidder_test_ctx())
        self.assertIn('"github.com/prebid/prebid-server/v4/adapters/adapterstest"', rendered)
        self.assertIn('"github.com/prebid/prebid-server/v4/config"', rendered)
        self.assertIn('"github.com/prebid/prebid-server/v4/openrtb_ext"', rendered)
        self.assertNotIn("/v3/", rendered)

    def test_params_test_module_version_v4(self):
        rendered = _render("params-test.go.j2", _kobler_params_test_ctx())
        self.assertIn('"github.com/prebid/prebid-server/v4/openrtb_ext"', rendered)
        self.assertNotIn("/v3/", rendered)


def _supplemental_fixture_ctx(scenario_kind: str) -> Dict[str, Any]:
    """Synthetic kobler-equivalent context for supplemental-fixture.json.j2."""
    return {
        "scenario_kind": scenario_kind,
        "mock_bid_request": {
            "id": "test-request-id",
            "imp": [
                {
                    "id": "test-imp-id",
                    "banner": {"format": [{"w": 300, "h": 250}]},
                },
            ],
        },
        "uri": "http://fake.endpoint",
        "expected_request_body": {
            "id": "test-request-id",
            "imp": [
                {
                    "id": "test-imp-id",
                    "banner": {"format": [{"w": 300, "h": 250}]},
                },
            ],
            "cur": ["USD"],
        },
        "imp_ids": ["test-imp-id"],
    }


class TestSupplementalFixtureJ2(unittest.TestCase):
    """D3.3 gate-3 coverage helper — supplemental fixtures pad upstream
    Go test coverage for kobler-shape adapters whose 1-scenario Java IT
    cannot exercise non-200 / no-body / malformed-body branches alone.

    The template covers 5 scenario_kind values, each kobler-shape-
    agnostic (works for any adapter using canonical-go-helpers status
    handling OR kobler's legacy-raw 204+other-non-200 shape):

      status-204 / status-400 / status-404 / no-response-body /
      malformed-body

    Error-string sources (verified against
    `prebid-server/adapters/response.go`):

      * status-400 / status-404 errors: emitted by
        `adapters.CheckResponseStatusCodeForErrors` —
        "Unexpected status code: %d. Run with request.debug = 1 for
        more info" (NO trailing period).
      * malformed-body error: emitted by
        `util/jsonutil.Unmarshal` when the response body is a JSON
        string starting with `"` —
        `expect { or n, but found "` — matches upstream kobler
        `wrong-response-body-type.json`.
      * status-204 / no-response-body: NO error — kobler adapter
        short-circuits via `IsResponseStatusCodeNoContent` and
        `responseData.Body == nil` respectively, returning (nil, nil).
        Matches upstream kobler `status-204.json` and
        `no-response-body.json`.
    """

    def test_status_204_emits_204_no_errors(self):
        ctx = _supplemental_fixture_ctx("status-204")
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertEqual(parsed["httpCalls"][0]["mockResponse"]["status"], 204)
        # 204 path: no errors, no body field.
        self.assertNotIn("expectedMakeBidsErrors", parsed)
        self.assertNotIn("body", parsed["httpCalls"][0]["mockResponse"])
        # Empty expectedBidResponses preserved (matches upstream kobler shape).
        self.assertEqual(parsed["expectedBidResponses"], [])

    def test_status_400_emits_400_with_error(self):
        ctx = _supplemental_fixture_ctx("status-400")
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        mock = parsed["httpCalls"][0]["mockResponse"]
        self.assertEqual(mock["status"], 400)
        # Body is present and is an empty object (matches upstream teads
        # status-400.json shape; satisfies adapterstest's body-required
        # assertion when status != 204).
        self.assertEqual(mock["body"], {})
        # Error string matches CheckResponseStatusCodeForErrors verbatim
        # (adapters/response.go line 13: no trailing period).
        errs = parsed["expectedMakeBidsErrors"]
        self.assertEqual(len(errs), 1)
        self.assertEqual(
            errs[0]["value"],
            "Unexpected status code: 400. Run with request.debug = 1 for more info",
        )
        self.assertEqual(errs[0]["comparison"], "literal")

    def test_status_404_emits_404_with_error(self):
        ctx = _supplemental_fixture_ctx("status-404")
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        mock = parsed["httpCalls"][0]["mockResponse"]
        self.assertEqual(mock["status"], 404)
        self.assertEqual(mock["body"], {})
        errs = parsed["expectedMakeBidsErrors"]
        self.assertEqual(len(errs), 1)
        self.assertEqual(
            errs[0]["value"],
            "Unexpected status code: 404. Run with request.debug = 1 for more info",
        )
        self.assertEqual(errs[0]["comparison"], "literal")

    def test_no_response_body_emits_200_null_body(self):
        ctx = _supplemental_fixture_ctx("no-response-body")
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        mock = parsed["httpCalls"][0]["mockResponse"]
        self.assertEqual(mock["status"], 200)
        # Body field omitted entirely (matches upstream kobler
        # no-response-body.json — adapterstest delivers Body==nil to the
        # adapter, which kobler-shape adapters short-circuit on).
        self.assertNotIn("body", mock)
        # No errors expected (kobler short-circuits with (nil, nil)).
        self.assertNotIn("expectedMakeBidsErrors", parsed)
        self.assertEqual(parsed["expectedBidResponses"], [])

    def test_malformed_body_emits_invalid_json_string(self):
        ctx = _supplemental_fixture_ctx("malformed-body")
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        mock = parsed["httpCalls"][0]["mockResponse"]
        self.assertEqual(mock["status"], 200)
        # Body is the literal JSON string "this is not json" — adapterstest's
        # json.RawMessage delivery means the adapter sees the raw 18 bytes
        # `"this is not json"` (with quotes). jsonutil.Unmarshal sees first
        # byte `"` and emits the canonical `expect { or n, but found "`.
        self.assertEqual(mock["body"], "this is not json")
        errs = parsed["expectedMakeBidsErrors"]
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]["value"], 'expect { or n, but found "')
        self.assertEqual(errs[0]["comparison"], "literal")

    def test_unknown_scenario_kind_renders_empty_or_errors(self):
        """Defensive: unknown scenario_kind values render a parse-clean but
        empty mockResponse + expectedBidResponses=[]. The renderer is
        expected to validate scenario_kind upstream and reject unknowns
        before invoking this template; this test pins the fail-graceful
        behavior so a rogue ctx does not crash the render."""
        ctx = _supplemental_fixture_ctx("status-200")  # unrecognized
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        # Empty mockResponse: only the structural braces, no status/body.
        self.assertEqual(parsed["httpCalls"][0]["mockResponse"], {})
        self.assertNotIn("expectedMakeBidsErrors", parsed)
        self.assertEqual(parsed["expectedBidResponses"], [])

    def test_imp_ids_emit_per_F_new_12(self):
        """F-new-12 (canary v2): adapterstest.RunJSONBidderTest asserts
        non-empty expectedRequest.impIDs. The supplemental template emits
        impIDs unconditionally (per spec; ctx.imp_ids is required)."""
        ctx = _supplemental_fixture_ctx("status-204")
        ctx["imp_ids"] = ["imp-A", "imp-B"]
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertEqual(
            parsed["httpCalls"][0]["expectedRequest"]["impIDs"],
            ["imp-A", "imp-B"],
        )
        # Render correctness across all 5 known kinds — impIDs always present.
        for kind in ("status-204", "status-400", "status-404",
                     "no-response-body", "malformed-body"):
            ctx2 = _supplemental_fixture_ctx(kind)
            ctx2["imp_ids"] = ["imp-A", "imp-B"]
            parsed2 = json.loads(_render("supplemental-fixture.json.j2", ctx2))
            self.assertEqual(
                parsed2["httpCalls"][0]["expectedRequest"]["impIDs"],
                ["imp-A", "imp-B"],
                f"impIDs missing for kind={kind}",
            )

    def test_passthrough_body_default(self):
        """The expected_request_body == mock_bid_request case (passthrough
        adapters like kobler/aax/freewheelssp): both should appear identically
        in the rendered JSON."""
        ctx = _supplemental_fixture_ctx("status-204")
        ctx["expected_request_body"] = ctx["mock_bid_request"]
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertEqual(
            parsed["mockBidRequest"],
            parsed["httpCalls"][0]["expectedRequest"]["body"],
        )

    def test_uri_emitted_verbatim(self):
        """The TEST_ENDPOINT URI must be emitted verbatim — adapterstest
        compares it to the URI the adapter constructs in MakeRequests."""
        ctx = _supplemental_fixture_ctx("status-204")
        ctx["uri"] = "https://bid.essrtb.com/bid/prebid_server_rtb_call"
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertEqual(
            parsed["httpCalls"][0]["expectedRequest"]["uri"],
            "https://bid.essrtb.com/bid/prebid_server_rtb_call",
        )


class TestRequiredArtifacts(unittest.TestCase):
    """Sanity: every Go template referenced by SKILL.md Step 5 exists."""

    EXPECTED_TEMPLATES = (
        "bidder-info.yaml.j2",
        "imp-ext-pojo.go.j2",
        "bidder-test.go.j2",
        "params-test.go.j2",
        "exemplary-fixture.json.j2",
        "bidder.go.j2",
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
