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
import shutil
import subprocess
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
        "endpoint": KOBLER_ENDPOINT,
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

# One endpoint for every kobler-shape fixture in this module. RunJSONBidderTest
# builds the adapter with the endpoint from the bidder-test ctx and then compares
# the request the adapter produced against each fixture's expectedRequest.uri, so
# a placeholder in any one of these contexts fails the run with
# `httpRequest[0].uri ... does not match expected`. 241 of the 247 upstream
# adapters that have both a Builder endpoint and exemplary uris match (97%).
KOBLER_ENDPOINT = "https://bid.essrtb.com/bid/prebid_server_rtb_call"

# bidder.go.j2 and supplemental-fixture.json.j2 both branch on this. The fixture's
# expectations only match the emitted adapter when both read the same value, so it
# is declared once. "canonical-go-helpers" is the behavior-taxonomy spelling that a
# source spec's code.make_bids.http_status_handling.kind actually carries.
KOBLER_HTTP_STATUS_KIND = "canonical-go-helpers"


def _kobler_bidder_test_ctx() -> Dict[str, Any]:
    return {
        "package_name": "kobler",
        "bidder_constant": "openrtb_ext.BidderKobler",
        "bidder_class_root": "Kobler",
        "module_version": GO_MODULE_VERSION,
        # Must equal _kobler_exemplary_fixture_ctx()'s http_calls[0].uri --
        # RunJSONBidderTest builds the adapter with this endpoint and then
        # compares the request it produced against the fixture's uri.
        "endpoint": KOBLER_ENDPOINT,
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
    # Each imp carries ext.bidder. 1369 of 1413 upstream exemplary fixtures with
    # an imp do (96%), and 173 of the 215 adapters that unmarshal imp.Ext (80%)
    # do it unguarded -- so an imp without ext makes MakeRequests return
    # `failed parsing imp.ext` and RunJSONBidderTest fails on the fixture the
    # same skill emitted. Omitting it is only safe for the 19% that nil-guard,
    # which upstream kobler happens to be.
    request = {
        "id": "req-1",
        "imp": [{
            "id": "imp-1",
            "banner": {"format": [{"w": 300, "h": 250}]},
            "ext": {"bidder": {"test": False}},
        }],
    }
    return {
        "mock_bid_request": request,
        "http_calls": [
            {
                "uri": KOBLER_ENDPOINT,
                # The emitted kobler-shape adapter forwards the request
                # unmodified, so the body it sends is the request it was given.
                # A stub body here ({"id": "req-1"}) makes the harness report
                # `Expected RequestData was not returned` on a correct adapter.
                "body": request,
                # adapterstest rejects a fixture whose expectedRequest has no
                # impIDs before comparing anything (test_json.go:359).
                "imp_ids": ["imp-1"],
                "status": 200,
                # The mock response sets `cur`. bidder.go.j2 assigns
                # bidderResponse.Currency = bidResponse.Cur unguarded, which is
                # the corpus norm (101 of 141 adapters, 71%), so it clobbers the
                # "USD" that NewBidderResponse seeds. Among those 101 adapters'
                # 515 exemplary fixtures, 290 (56%) set `cur` to match the
                # asserted currency and 214 (41%) assert no currency; only 11
                # (2%) assert one the mock never sets, and that pair fails
                # RunJSONBidderTest with `Got , expected USD`.
                "response": {"id": "resp-1", "cur": "USD",
                             "seatbid": [{"bid": [{"id": "bid-1", "impid": "imp-1", "price": 1.5}]}]},
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
        "http_status_kind": KOBLER_HTTP_STATUS_KIND,
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
        self.assertEqual(parsed["endpoint"], KOBLER_ENDPOINT)

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
                         KOBLER_ENDPOINT)
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

    def test_imp_ids_are_required_not_optional(self):
        """adapterstest rejects a fixture whose expectedRequest carries no
        impIDs before it compares anything:

            if len(expected.ImpIDs) < 1 {
                return fmt.Errorf(`expected.ImpIDs must contain at least one imp ID`)
            }

        (adapters/adapterstest/test_json.go:359 at 0ba35231.) All 2820 upstream
        fixtures that declare an httpCall carry impIDs. An earlier review asked
        for the key to be omitted when the ctx did not supply it, which made the
        two fixture templates agree with each other and both emit fixtures the
        harness refuses to run -- `expected.ImpIDs must contain at least one imp
        ID`, before any request or response comparison. The template now fails
        at render instead.
        """
        ctx = _kobler_exemplary_fixture_ctx()
        for call in ctx["http_calls"]:
            call.pop("imp_ids", None)
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("exemplary-fixture.json.j2", ctx)
        self.assertIn("ERROR_every_http_call_requires_imp_ids", str(cm.exception))

    def test_imp_ids_emitted_for_every_http_call(self):
        rendered = _render("exemplary-fixture.json.j2", _kobler_exemplary_fixture_ctx())
        parsed = json.loads(rendered)
        for call in parsed["httpCalls"]:
            self.assertTrue(call["expectedRequest"]["impIDs"],
                            "every expectedRequest needs a non-empty impIDs")


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
        # "legacy-raw-go" is the behavior-taxonomy value. The template's Inputs
        # block used to also list "legacy-raw", which no branch consumed -- it
        # reached the raw checks only by falling through, the same path a typo
        # took. It is now rejected.
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw-go"
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

    # ----------------- F-new-1: imp_ext_unmarshal_kind=="none" --------------
    # Affects ~12% of corpus (aax, optidigital). When imp.ext.bidder has no
    # required schema fields the adapter forwards the request without
    # inspecting imp.ext, so neither the per-imp parseImpExt() call nor the
    # parseImpExt helper function should be emitted.

    def test_imp_ext_unmarshal_none_skips_parseImpExt_call(self):
        """F-new-1: with imp_ext_unmarshal_kind='none' the per-imp
        parseImpExt(...) call MUST NOT appear in MakeRequests body."""
        ctx = _kobler_bidder_go_ctx()
        ctx["imp_ext_unmarshal_kind"] = "none"
        # Disable currency conversion so the single-batched loop has no
        # other per-imp work and collapses entirely (matches upstream aax).
        ctx["uses_currency_conversion"] = False
        rendered = _render("bidder.go.j2", ctx)
        self.assertNotIn("parseImpExt", rendered)

    def test_imp_ext_unmarshal_none_skips_parseImpExt_helper(self):
        """F-new-1: the parseImpExt helper function declaration MUST NOT
        emit when imp_ext_unmarshal_kind='none' (else Go raises an
        unused-function compile error / lint warning)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["imp_ext_unmarshal_kind"] = "none"
        ctx["uses_currency_conversion"] = False
        rendered = _render("bidder.go.j2", ctx)
        self.assertNotIn("func parseImpExt", rendered)

    def test_imp_ext_unmarshal_standard_two_phase_unchanged(self):
        """F-new-1 regression: existing 'standard-two-phase' branch
        unchanged — kobler default ctx still emits both call AND helper."""
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        # Per-imp call site present.
        self.assertIn("parseImpExt(&request.Imp[i])", rendered)
        # Helper function declaration present.
        self.assertIn("func parseImpExt(imp *openrtb2.Imp)", rendered)
        # Two-phase body present.
        self.assertIn("var bidderExt adapters.ExtImpBidder", rendered)

    def test_imp_ext_unmarshal_none_with_currency_conversion_keeps_loop(self):
        """F-new-1 partner case: imp_ext_unmarshal='none' AND
        uses_currency_conversion=True → loop is preserved (currency call
        still runs per-imp), but parseImpExt call is dropped from inside."""
        ctx = _kobler_bidder_go_ctx()
        ctx["imp_ext_unmarshal_kind"] = "none"
        ctx["uses_currency_conversion"] = True
        rendered = _render("bidder.go.j2", ctx)
        # Loop still emits because currency conversion is still per-imp work.
        self.assertIn("for i := range request.Imp", rendered)
        self.assertIn("convertImpCurrency(&request.Imp[i]", rendered)
        # parseImpExt absent.
        self.assertNotIn("parseImpExt", rendered)

    def test_imp_ext_unmarshal_none_per_imp_batching(self):
        """F-new-1 with per-imp batching: outer loop is structural (builds
        per-imp requests), so it stays. Just the parseImpExt block goes."""
        ctx = _kobler_bidder_go_ctx()
        ctx["imp_ext_unmarshal_kind"] = "none"
        ctx["uses_currency_conversion"] = False
        ctx["batching_kind"] = "per-imp"
        rendered = _render("bidder.go.j2", ctx)
        # Loop kept.
        self.assertIn("for i := range request.Imp", rendered)
        self.assertIn("perImp := *request", rendered)
        # parseImpExt absent.
        self.assertNotIn("parseImpExt", rendered)

    # ------------- F-new-14: legacy-raw-go per-status branching -----------
    # Affects ~3/16 (19%) of corpus. Legacy-raw-go adapters that have
    # bidder-specific status handling (aax: 204/400/other) need per-status
    # branches with errortypes.{BadInput,BadServerResponse,...}.

    def test_legacy_raw_with_status_handlers_emits_per_status_branches(self):
        """F-new-14 baseline: a single 400->BadInput handler emits the 204
        short-circuit AND the StatusBadRequest BadInput branch."""
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw-go"
        ctx["legacy_raw_status_handlers"] = [
            {"status_code": 400, "error_kind": "BadInput"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        # 204 short-circuit always present in legacy-raw-go.
        self.assertIn("responseData.StatusCode == http.StatusNoContent", rendered)
        # 400 -> BadInput branch.
        self.assertIn("responseData.StatusCode == http.StatusBadRequest", rendered)
        self.assertIn("&errortypes.BadInput{", rendered)
        self.assertIn(
            "Unexpected status code: %d. Run with request.debug = 1 for more info",
            rendered,
        )
        # Catchall flips from generic fmt.Errorf to BadServerResponse.
        self.assertIn("&errortypes.BadServerResponse{", rendered)
        self.assertIn("responseData.StatusCode != http.StatusOK", rendered)
        # Generic legacy-raw fmt.Errorf string MUST NOT appear when handlers populated.
        self.assertNotIn('fmt.Errorf("unexpected status code: %d"', rendered)

    def test_legacy_raw_status_handlers_3branch_aax_shape(self):
        """F-new-14 aax shape: 204 -> return nil; 400 -> BadInput;
        other-non-200 -> BadServerResponse. Verify all three branches appear
        in declared order with the correct errortypes."""
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw-go"
        ctx["legacy_raw_status_handlers"] = [
            {"status_code": 400, "error_kind": "BadInput"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        # Lexical ordering matches upstream aax.go exactly.
        no_content_idx = rendered.index("responseData.StatusCode == http.StatusNoContent")
        bad_request_idx = rendered.index("responseData.StatusCode == http.StatusBadRequest")
        bad_input_idx = rendered.index("&errortypes.BadInput{")
        not_ok_idx = rendered.index("responseData.StatusCode != http.StatusOK")
        bad_server_idx = rendered.index("&errortypes.BadServerResponse{")
        self.assertLess(no_content_idx, bad_request_idx)
        self.assertLess(bad_request_idx, bad_input_idx)
        self.assertLess(bad_input_idx, not_ok_idx)
        self.assertLess(not_ok_idx, bad_server_idx)

    def test_legacy_raw_status_handlers_multi_status_in_declared_order(self):
        """F-new-14 ordering: multiple handlers emit in declaration order,
        not sorted by status code (operator controls precedence)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw-go"
        ctx["legacy_raw_status_handlers"] = [
            {"status_code": 404, "error_kind": "BadInput"},
            {"status_code": 400, "error_kind": "BadInput"},
            {"status_code": 429, "error_kind": "BadServerResponse"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        i_404 = rendered.index("http.StatusNotFound")
        i_400 = rendered.index("http.StatusBadRequest")
        i_429 = rendered.index("http.StatusTooManyRequests")
        # Declared order: 404, 400, 429.
        self.assertLess(i_404, i_400)
        self.assertLess(i_400, i_429)

    def test_legacy_raw_no_handlers_uses_2branch_default(self):
        """F-new-14 backward compat: legacy-raw-go without handlers (None)
        falls back to the existing 2-branch shape (matches legacy-raw)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw-go"
        ctx["legacy_raw_status_handlers"] = None
        rendered = _render("bidder.go.j2", ctx)
        # 204 + non-200 generic — same as the bare legacy-raw branch.
        self.assertIn("responseData.StatusCode == http.StatusNoContent", rendered)
        self.assertIn(
            'return nil, []error{fmt.Errorf("unexpected status code: %d"',
            rendered,
        )
        # No errortypes branches emitted.
        self.assertNotIn("errortypes", rendered)

    def test_legacy_raw_empty_handlers_uses_2branch_default(self):
        """F-new-14 backward compat: empty list also preserves 2-branch."""
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw-go"
        ctx["legacy_raw_status_handlers"] = []
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn(
            'return nil, []error{fmt.Errorf("unexpected status code: %d"',
            rendered,
        )
        self.assertNotIn("errortypes", rendered)

    def test_canonical_helpers_ignores_legacy_raw_field(self):
        """F-new-14 isolation: with http_status_kind='canonical-helpers'
        the legacy_raw_status_handlers field is silently ignored — caller
        ctx is not validated, but the canonical-helpers branch is rendered
        unchanged (no errortypes import, no per-status branches)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "canonical-helpers"
        ctx["legacy_raw_status_handlers"] = [
            {"status_code": 400, "error_kind": "BadInput"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        # Canonical-helpers branch active.
        self.assertIn("adapters.IsResponseStatusCodeNoContent(responseData)", rendered)
        self.assertIn("adapters.CheckResponseStatusCodeForErrors(responseData)", rendered)
        # Per-status branches NOT emitted.
        self.assertNotIn("&errortypes.BadInput{", rendered)
        self.assertNotIn("&errortypes.BadServerResponse{", rendered)
        # And the errortypes import line is absent.
        self.assertNotIn("/v4/errortypes", rendered)

    def test_errortypes_import_emit_when_handlers_populated(self):
        """F-new-14 import gating: errortypes import line emits ONLY when
        legacy-raw-go AND handlers are populated."""
        # Case 1: handlers populated -> import present.
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = "legacy-raw-go"
        ctx["legacy_raw_status_handlers"] = [
            {"status_code": 400, "error_kind": "BadInput"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn(
            '"github.com/prebid/prebid-server/v4/errortypes"',
            rendered,
        )

        # Case 2: legacy-raw-go without handlers -> no import.
        ctx2 = _kobler_bidder_go_ctx()
        ctx2["http_status_kind"] = "legacy-raw-go"
        ctx2["legacy_raw_status_handlers"] = None
        rendered2 = _render("bidder.go.j2", ctx2)
        self.assertNotIn("/v4/errortypes", rendered2)

        # Case 3: canonical-helpers with handlers -> no import.
        ctx3 = _kobler_bidder_go_ctx()
        ctx3["http_status_kind"] = "canonical-helpers"
        ctx3["legacy_raw_status_handlers"] = [
            {"status_code": 400, "error_kind": "BadInput"},
        ]
        rendered3 = _render("bidder.go.j2", ctx3)
        self.assertNotIn("/v4/errortypes", rendered3)

    def test_legacy_raw_status_handlers_aax_full_combination(self):
        """F-new-14 + F-new-1 integration: full aax shape — imp_ext='none',
        legacy-raw-go with 400->BadInput, no currency conversion, 3-step
        method-chain bid type. Verifies the two findings compose cleanly."""
        ctx = _kobler_bidder_go_ctx()
        ctx["imp_ext_unmarshal_kind"] = "none"
        ctx["uses_currency_conversion"] = False
        ctx["http_status_kind"] = "legacy-raw-go"
        ctx["legacy_raw_status_handlers"] = [
            {"status_code": 400, "error_kind": "BadInput"},
        ]
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {"method": "by-bid-ext-typed-field", "field": "bid.ext.adCodeType",
             "fallback_action": "next"},
            {"method": "by-imp-mediatype", "fallback_action": "next"},
            {"method": "throw"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        # F-new-1: parseImpExt absent, no per-imp loop.
        self.assertNotIn("parseImpExt", rendered)
        self.assertNotIn("for i := range request.Imp", rendered)
        # F-new-14: 3-branch status handling.
        self.assertIn("&errortypes.BadInput{", rendered)
        self.assertIn("&errortypes.BadServerResponse{", rendered)
        # 3-step bid-type chain produces error-returning signature.
        self.assertIn("(openrtb_ext.BidType, error)", rendered)
        # Errortypes import.
        self.assertIn(
            '"github.com/prebid/prebid-server/v4/errortypes"',
            rendered,
        )


class TestEndpointResolutionMacros(unittest.TestCase):
    """F-new-2 / F-new-27 — bidder.go.j2 resolveEndpoint covers the
    `template-macro` and `multi-token-substitution` kinds, replacing the
    previous TODO-stub fall-through with the canonical Go
    `macros.ResolveMacros` pattern.

    The two kinds are mechanically identical in the emit (both use
    `text/template` + `macros.EndpointTemplateParams` + `ResolveMacros`);
    they differ only in the *number* of macros (`template-macro` ≈ 1,
    `multi-token-substitution` ≈ N>=2). The template branch keys off the
    union of both kinds via `_endpoint_needs_macros_resolution`.

    Upstream canonical references:
      - adapters/adkernelAdn/adkernelAdn.go::buildEndpointURL (1 macro)
      - adapters/thetradedesk/thetradedesk.go::buildEndpointURL (1 macro)
      - adapters/adverxo/adverxo.go::buildEndpointURL (2 macros, mixed
        int+string conversions)
    """

    def _base_ctx(self) -> Dict[str, Any]:
        """Shared ctx baseline mirroring the adkernelAdn-shape that all 3
        canaries (adkernelAdn, thetradedesk, adverxo) lean on. Subclasses
        override `endpoint_resolution_kind`, `endpoint_macros`,
        `imports_extra` per shape."""
        return {
            "package_name": "demobidder",
            "bidder_class_root": "Demobidder",
            "uses_currency_conversion": False,
            "imp_ext_class_root": "Demobidder",
            "imp_ext_unmarshal_kind": "standard-two-phase",
            "batching_kind": "single-batched",
            "batching_max_imps": None,
            "endpoint_resolution_kind": "template-macro",
            "http_status_kind": KOBLER_HTTP_STATUS_KIND,
            "bid_type_resolution": "imp-mediatype-introspection",
            "has_extra_info": False,
            "module_version": GO_MODULE_VERSION,
            "imports_extra": [],
            "javadoc_summary": None,
            "endpoint_macros": [],
        }

    # ----------------------- imports + struct wiring ---------------------

    def test_template_macro_imports_text_template_and_macros(self):
        """F-new-2: template-macro must add `"text/template"` and
        `"github.com/prebid/prebid-server/{v}/macros"` to the import block."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "PublisherID", "ext_field": "PublisherID",
             "convert": "itoa"},
        ]
        ctx["imports_extra"] = ["strconv"]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn('"text/template"', rendered)
        self.assertIn('"github.com/prebid/prebid-server/v4/macros"', rendered)

    def test_multi_token_imports_text_template_and_macros(self):
        """F-new-27: same import set for multi-token-substitution."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "multi-token-substitution"
        ctx["endpoint_macros"] = [
            {"macro": "AdUnit", "ext_field": "AdUnitId", "convert": "itoa"},
            {"macro": "TokenID", "ext_field": "Auth", "convert": None},
        ]
        ctx["imports_extra"] = ["strconv"]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn('"text/template"', rendered)
        self.assertIn('"github.com/prebid/prebid-server/v4/macros"', rendered)

    def test_adapter_struct_gains_endpoint_template_field(self):
        """F-new-2: adapter struct gains `EndpointTemplate *template.Template`
        field when macros-resolution active. Field name PascalCase per
        upstream adkernelAdn shape (deliberate — exported, though Go-private
        use; mirrors upstream choice)."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "PublisherID", "ext_field": "PublisherID",
             "convert": "itoa"},
        ]
        ctx["imports_extra"] = ["strconv"]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("EndpointTemplate *template.Template", rendered)

    # ----------------------- Builder template parse ----------------------

    def test_builder_parses_endpoint_template(self):
        """F-new-2: Builder must call `template.New(...).Parse(cfg.Endpoint)`
        and return fmt.Errorf on parse failure. Matches upstream
        adkernelAdn.go::Builder shape."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "PublisherID", "ext_field": "PublisherID",
             "convert": "itoa"},
        ]
        ctx["imports_extra"] = ["strconv"]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn(
            'template.New("demobidderEndpointTemplate").Parse(cfg.Endpoint)',
            rendered,
        )
        self.assertIn(
            'fmt.Errorf("unable to parse endpoint url template: %v", err)',
            rendered,
        )
        # Field is wired onto the adapter.
        self.assertIn("a.EndpointTemplate = tpl", rendered)

    # ----------------------- resolveEndpoint body ------------------------

    def test_template_macro_single_macro_emits_macros_resolve(self):
        """F-new-2 baseline (adkernelAdn shape): template-macro with a single
        macro (`PublisherID`) emits the canonical macros.ResolveMacros
        body — parse imp.ext, build EndpointTemplateParams, call
        ResolveMacros. The signature flips to `(string, error)`."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "PublisherID", "ext_field": "PublisherID",
             "convert": "itoa"},
        ]
        ctx["imports_extra"] = ["strconv"]
        rendered = _render("bidder.go.j2", ctx)
        # Signature flipped to (string, error).
        self.assertIn(
            "func (a *adapter) resolveEndpoint(request *openrtb2.BidRequest) (string, error)",
            rendered,
        )
        # Old no-error signature absent.
        self.assertNotIn(
            "func (a *adapter) resolveEndpoint(request *openrtb2.BidRequest) string",
            rendered,
        )
        # impExt parse + macros struct populated + ResolveMacros call.
        self.assertIn("impExt, err := parseImpExt(&request.Imp[0])", rendered)
        self.assertIn("endpointParams := macros.EndpointTemplateParams{", rendered)
        self.assertIn("PublisherID: strconv.Itoa(impExt.PublisherID),", rendered)
        self.assertIn(
            "return macros.ResolveMacros(a.EndpointTemplate, endpointParams)",
            rendered,
        )

    def test_multi_token_two_macros_emit_in_declared_order(self):
        """F-new-27 baseline (adverxo shape): multi-token-substitution with
        two macros (`AdUnit` int + `TokenID` string) emits both fields in
        declared order. Mixed-conversion case — first macro uses itoa,
        second is raw string."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "multi-token-substitution"
        ctx["endpoint_macros"] = [
            {"macro": "AdUnit", "ext_field": "AdUnitId", "convert": "itoa"},
            {"macro": "TokenID", "ext_field": "Auth", "convert": None},
        ]
        ctx["imports_extra"] = ["strconv"]
        rendered = _render("bidder.go.j2", ctx)
        # Both macros emit with correct conversions.
        self.assertIn("AdUnit: strconv.Itoa(impExt.AdUnitId),", rendered)
        self.assertIn("TokenID: impExt.Auth,", rendered)
        # Declared order: AdUnit before TokenID.
        ad_unit_idx = rendered.index("AdUnit: strconv.Itoa")
        token_id_idx = rendered.index("TokenID: impExt.Auth")
        self.assertLess(ad_unit_idx, token_id_idx)
        # ResolveMacros call present.
        self.assertIn(
            "return macros.ResolveMacros(a.EndpointTemplate, endpointParams)",
            rendered,
        )

    def test_template_macro_string_macro_no_convert(self):
        """F-new-2 (thetradedesk shape): template-macro with a single
        string-typed macro (`SupplyId` from a string ext field). When
        `convert` is None/omitted, the value emits as raw `impExt.<field>`
        with no wrapping. Mirrors upstream thetradedesk.go::buildEndpointURL."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "SupplyId", "ext_field": "PublisherId", "convert": None},
        ]
        # No strconv needed — ext_field is string-typed.
        ctx["imports_extra"] = []
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("SupplyId: impExt.PublisherId,", rendered)
        # No strconv import or call.
        self.assertNotIn("strconv.Itoa", rendered)

    # ------------------------ callsite error-handling --------------------

    def test_callsite_single_batched_handles_error(self):
        """F-new-2: single-batched MakeRequests callsite binds the error
        from resolveEndpoint and appends to the errors slice."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "PublisherID", "ext_field": "PublisherID",
             "convert": "itoa"},
        ]
        ctx["imports_extra"] = ["strconv"]
        ctx["batching_kind"] = "single-batched"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("uri, err := a.resolveEndpoint(request)", rendered)
        self.assertIn("return nil, append(errors, err)", rendered)
        # Uri field uses bound variable, not direct call.
        self.assertRegex(rendered, r"Uri:\s+uri,")

    def test_callsite_per_imp_handles_error(self):
        """F-new-2: per-imp batching MakeRequests callsite binds the
        resolveEndpoint error per-imp; on error, `continue` skips that
        imp's RequestData."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "multi-token-substitution"
        ctx["endpoint_macros"] = [
            {"macro": "AdUnit", "ext_field": "AdUnitId", "convert": "itoa"},
            {"macro": "TokenID", "ext_field": "Auth", "convert": None},
        ]
        ctx["imports_extra"] = ["strconv"]
        ctx["batching_kind"] = "per-imp"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("uri, err := a.resolveEndpoint(&perImp)", rendered)
        # Per-imp loop body has `continue` on resolveEndpoint error.
        self.assertIn("errors = append(errors, err)", rendered)
        # Uri field uses the bound variable (spacing is gofmt-controlled —
        # match the bare `Uri:` + `uri,` pair, not exact whitespace).
        self.assertRegex(rendered, r"Uri:\s+uri,")

    def test_callsite_max_imps_handles_error(self):
        """F-new-2: max-imps-per-request batching MakeRequests callsite
        binds the resolveEndpoint error per-chunk; on error, `continue`
        skips that chunk's RequestData. Regression guard for the audit
        review's MINOR-flagged missing max-imps coverage."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "PublisherID", "ext_field": "PublisherID", "convert": "itoa"},
        ]
        ctx["imports_extra"] = ["strconv"]
        ctx["batching_kind"] = "max-imps-per-request"
        ctx["batching_max_imps"] = 5
        rendered = _render("bidder.go.j2", ctx)
        # max-imps branch resolves endpoint per-chunk; error binding required.
        self.assertIn("uri, err := a.resolveEndpoint(", rendered)
        self.assertIn("errors = append(errors, err)", rendered)
        # Uri field uses the bound variable.
        self.assertRegex(rendered, r"Uri:\s+uri,")
        # max-imps chunker helper still emits (backward-compat).
        self.assertIn("func chunkImps(", rendered)

    # ------------------------ empty-macros TODO ------------------------

    def test_empty_endpoint_macros_emits_todo_with_wiring(self):
        """F-new-2 staged emit: when ctx.endpoint_macros is empty / None,
        the wiring (struct field, Builder Parse, imports, ResolveMacros
        call) still emits but the EndpointTemplateParams struct is empty
        and a TODO comment cues the operator. Useful for pre-pass emit
        before the operator has populated macros_used."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = []
        rendered = _render("bidder.go.j2", ctx)
        # Wiring present.
        self.assertIn("EndpointTemplate *template.Template", rendered)
        self.assertIn('"text/template"', rendered)
        # Empty struct.
        self.assertIn("endpointParams := macros.EndpointTemplateParams{}", rendered)
        # TODO comment cues the operator at the right schema field.
        self.assertIn(
            "TODO[port-java2go]: ctx.endpoint_macros is empty",
            rendered,
        )
        # ResolveMacros still invoked.
        self.assertIn(
            "macros.ResolveMacros(a.EndpointTemplate, endpointParams)",
            rendered,
        )

    def test_empty_endpoint_macros_skips_imp_parse(self):
        """F-new-2: empty endpoint_macros means we have no impExt fields to
        read — skip the parseImpExt call inside resolveEndpoint to avoid
        an unused-variable Go compile error. The per-imp parseImpExt is
        still in the per-imp loop (the bidder may need it for validation),
        but resolveEndpoint's local parse is gated on macros being
        present."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = []
        rendered = _render("bidder.go.j2", ctx)
        # Inside resolveEndpoint, no local impExt parse.
        resolve_idx = rendered.index("func (a *adapter) resolveEndpoint")
        # Body ends at next func (we'll just look at next 500 chars).
        body = rendered[resolve_idx:resolve_idx + 600]
        self.assertNotIn("impExt, err := parseImpExt", body)

    # ------------------------ kind isolation -----------------------------

    def test_other_endpoint_kinds_unaffected(self):
        """F-new-2 isolation: when endpoint_resolution_kind is `static` /
        `dev-prod-toggle` / `query-parameter-augmentation` /
        `single-token-substitution`, the macros-resolution wiring MUST
        NOT emit — old behavior preserved."""
        for kind in (
            "static",
            "dev-prod-toggle",
            "query-parameter-augmentation",
            "single-token-substitution",
        ):
            with self.subTest(kind=kind):
                ctx = self._base_ctx()
                ctx["endpoint_resolution_kind"] = kind
                rendered = _render("bidder.go.j2", ctx)
                # Macros-resolution artifacts absent.
                self.assertNotIn('"text/template"', rendered, kind)
                self.assertNotIn(
                    '"github.com/prebid/prebid-server/v4/macros"',
                    rendered,
                    kind,
                )
                self.assertNotIn("EndpointTemplate", rendered, kind)
                self.assertNotIn("macros.ResolveMacros", rendered, kind)
                # resolveEndpoint keeps the no-error signature.
                self.assertIn(
                    "func (a *adapter) resolveEndpoint(request *openrtb2.BidRequest) string",
                    rendered,
                    kind,
                )

    # ----------------------- conversion variants -------------------------

    def test_convert_format_int64_emits_strconv_formatint(self):
        """F-new-2 conversion variant: `convert: "format-int64"` emits the
        `strconv.FormatInt(impExt.X, 10)` wrapper. Useful when the ExtImp
        field is `int64` rather than plain `int` (Go strconv.Itoa rejects
        int64)."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "AccountID", "ext_field": "AccountId",
             "convert": "format-int64"},
        ]
        ctx["imports_extra"] = ["strconv"]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn(
            "AccountID: strconv.FormatInt(impExt.AccountId, 10),",
            rendered,
        )

    def test_convert_escape_hatch_passthrough(self):
        """F-new-2 escape hatch: when `convert` is set to a non-recognized
        value, the template treats it as a full Go expression and passes
        it through verbatim. Operator-vouched compile; useful for unusual
        type conversions outside the {None, itoa, format-int64} set."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "Host", "ext_field": "Host",
             "convert": 'strings.ToLower(impExt.Host)'},
        ]
        ctx["imports_extra"] = ["strings"]
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("Host: strings.ToLower(impExt.Host),", rendered)


class TestPerKeyBatching(unittest.TestCase):
    """F-new-7 EXT-A — `batching_kind == "per-key"` template branch.

    Per-key batching groups imps by their parsed `openrtb_ext.ExtImp{X}`
    value (the whole struct), then emits one outbound HTTP per group.
    Pattern cribbed from upstream `adapters/adkernelAdn/adkernelAdn.go::
    dispatchImpressions` + the MakeRequests per-batch loop.

    Composition with F-new-2 template-macro: when both fire, the per-batch
    endpoint is resolved against the parsed grouping-key struct (passed
    by pointer into `resolveEndpoint(*openrtb_ext.ExtImp{X})`), NOT against
    `request.Imp[0]` — mirrors upstream `buildEndpointURL(params)`.

    ctx schema additions (F-new-7 EXT-A):
      - ctx.batching_kind = "per-key"
      - ctx.batching_per_key = {
            "helper_name": str|None,   # default "dispatchImpressions"
            "key_field": str,          # informational (e.g., "PublisherID")
        }
    """

    def _base_ctx(self) -> Dict[str, Any]:
        """adkernelAdn-shape ctx baseline. Subclasses override
        `endpoint_resolution_kind` + `endpoint_macros` for the composition
        cases."""
        return {
            "package_name": "adkernelAdn",
            "bidder_class_root": "AdkernelAdn",
            "uses_currency_conversion": False,
            "imp_ext_class_root": "AdkernelAdn",
            "imp_ext_unmarshal_kind": "standard-two-phase",
            "batching_kind": "per-key",
            "batching_max_imps": None,
            "batching_per_key": {
                "helper_name": "dispatchImpressions",
                "key_field": "PublisherID",
            },
            "endpoint_resolution_kind": "template-macro",
            "endpoint_macros": [
                {"macro": "PublisherID", "ext_field": "PublisherID",
                 "convert": "itoa"},
            ],
            "http_status_kind": KOBLER_HTTP_STATUS_KIND,
            "bid_type_resolution": "imp-mediatype-introspection",
            "has_extra_info": False,
            "module_version": GO_MODULE_VERSION,
            "imports_extra": ["strconv"],
            "javadoc_summary": None,
        }

    # ------------------------- helper emission --------------------------

    def test_dispatchImpressions_helper_emits(self):
        """F-new-7 EXT-A baseline: per-key emits a `dispatchImpressions`
        helper that returns `map[ExtImp{X}][]openrtb2.Imp + []error`."""
        rendered = _render("bidder.go.j2", self._base_ctx())
        self.assertIn(
            "func dispatchImpressions(imps []openrtb2.Imp) "
            "(map[openrtb_ext.ExtImpAdkernelAdn][]openrtb2.Imp, []error)",
            rendered,
        )
        # Iterates imps, parses ext, groups by the struct value.
        self.assertIn("for i := range imps", rendered)
        self.assertIn("impExt, err := parseImpExt(&imps[i])", rendered)
        self.assertIn("groups[*impExt] = append(groups[*impExt], imps[i])", rendered)

    def test_helper_name_customizable(self):
        """F-new-7 EXT-A: operator can override `helper_name` for bidders
        with a non-canonical grouping-helper name."""
        ctx = self._base_ctx()
        ctx["batching_per_key"] = {
            "helper_name": "groupImpsByPublisher",
            "key_field": "PublisherID",
        }
        rendered = _render("bidder.go.j2", ctx)
        # The custom name appears in BOTH the func declaration AND the
        # MakeRequests callsite.
        self.assertIn("func groupImpsByPublisher(imps []openrtb2.Imp)", rendered)
        self.assertIn(
            "groups, dispErrs := groupImpsByPublisher(request.Imp)",
            rendered,
        )
        # Canonical name does NOT leak.
        self.assertNotIn("func dispatchImpressions(", rendered)

    def test_helper_name_defaults_to_dispatchImpressions_when_omitted(self):
        """F-new-7 EXT-A back-compat: when `helper_name` is omitted (or
        ctx.batching_per_key is the empty dict), the canonical upstream
        name `dispatchImpressions` is used."""
        ctx = self._base_ctx()
        ctx["batching_per_key"] = {"key_field": "PublisherID"}
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("func dispatchImpressions(", rendered)
        self.assertIn(
            "groups, dispErrs := dispatchImpressions(request.Imp)",
            rendered,
        )

    # ----------------- MakeRequests per-batch loop ----------------------

    def test_makerequests_emits_per_batch_loop(self):
        """F-new-7 EXT-A: MakeRequests body iterates `groups` and emits
        one adapters.RequestData per map bucket. ImpIDs are computed
        from the bucket's imps (NOT request.Imp)."""
        rendered = _render("bidder.go.j2", self._base_ctx())
        # Map iteration with key + value.
        self.assertIn("for key, batchImps := range groups", rendered)
        # Per-batch BidRequest shallow-copied.
        self.assertIn("perGroup := *request", rendered)
        self.assertIn("perGroup.Imp = batchImps", rendered)
        # ImpIDs derived from the bucket's imps.
        self.assertIn("ImpIDs:  openrtb_ext.GetImpIDs(perGroup.Imp)", rendered)
        # Empty-map short-circuit (matches upstream adkernelAdn shape).
        self.assertIn("if len(groups) == 0", rendered)

    # ------------------- composition with F-new-2 -----------------------

    def test_composition_template_macro_resolveEndpoint_takes_ext_pointer(self):
        """F-new-7 EXT-A + F-new-2: when per-key composes with
        template-macro endpoint resolution, the resolveEndpoint signature
        flips from `(*openrtb2.BidRequest) (string, error)` to
        `(*openrtb_ext.ExtImp{X}) (string, error)` — the per-batch
        endpoint is computed against the GROUPING-KEY struct (matches
        upstream adkernelAdn.go::buildEndpointURL)."""
        rendered = _render("bidder.go.j2", self._base_ctx())
        # Per-key + template-macro signature.
        self.assertIn(
            "func (a *adapter) resolveEndpoint(impExt *openrtb_ext.ExtImpAdkernelAdn) (string, error)",
            rendered,
        )
        # NOT the *openrtb2.BidRequest signature.
        self.assertNotIn(
            "func (a *adapter) resolveEndpoint(request *openrtb2.BidRequest)",
            rendered,
        )
        # Body builds EndpointTemplateParams from the impExt pointer
        # directly (no parseImpExt re-parse).
        self.assertIn(
            "endpointParams := macros.EndpointTemplateParams{",
            rendered,
        )
        self.assertIn(
            "PublisherID: strconv.Itoa(impExt.PublisherID),",
            rendered,
        )
        self.assertIn(
            "return macros.ResolveMacros(a.EndpointTemplate, endpointParams)",
            rendered,
        )
        # MakeRequests per-batch loop passes the &batchKey pointer.
        self.assertIn("uri, err := a.resolveEndpoint(&batchKey)", rendered)

    def test_composition_template_macro_no_imp0_reparse(self):
        """F-new-7 EXT-A + F-new-2: composition MUST NOT re-parse
        request.Imp[0].Ext inside resolveEndpoint — the grouping-key
        struct already carries the macro source fields. The
        `len(request.Imp) == 0` guard from the F-new-2 baseline body is
        absent in the per-key variant."""
        rendered = _render("bidder.go.j2", self._base_ctx())
        # Carve out the resolveEndpoint body.
        resolve_idx = rendered.index("func (a *adapter) resolveEndpoint")
        # Slice to next func or end.
        next_func = rendered.find("func ", resolve_idx + 5)
        body = rendered[resolve_idx:next_func]
        self.assertNotIn("parseImpExt(&request.Imp[0])", body)
        self.assertNotIn("len(request.Imp) == 0", body)

    # ------------------- non-template-macro variant ---------------------

    def test_per_key_with_static_endpoint_uses_a_endpoint(self):
        """F-new-7 EXT-A: per-key + non-template-macro endpoint reads
        `a.endpoint` directly inside the per-batch loop (no helper call).
        The `resolveEndpoint(*openrtb2.BidRequest)` helper is SUPPRESSED
        to avoid emitting an unused-function vet warning."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "static"
        ctx["endpoint_macros"] = None
        ctx["imports_extra"] = []
        rendered = _render("bidder.go.j2", ctx)
        # Direct read of `a.endpoint` inside the per-batch loop.
        self.assertIn("Uri:     a.endpoint,", rendered)
        # macros wiring absent.
        self.assertNotIn("text/template", rendered)
        self.assertNotIn("macros.ResolveMacros", rendered)
        # resolveEndpoint helper NOT emitted (else go vet would flag it
        # as unused).
        self.assertNotIn("func (a *adapter) resolveEndpoint", rendered)

    # --------------- forces parseImpExt helper to emit ------------------

    def test_per_key_forces_parseImpExt_helper(self):
        """F-new-7 EXT-A: dispatchImpressions calls parseImpExt per imp,
        so the parseImpExt helper MUST be emitted even when
        imp_ext_unmarshal_kind would otherwise suppress it. Without
        this force-enable the rendered Go would fail compilation with
        an undefined-symbol error."""
        ctx = self._base_ctx()
        # endpoint_resolution=static so F-new-2 doesn't also force-emit.
        ctx["endpoint_resolution_kind"] = "static"
        ctx["endpoint_macros"] = None
        ctx["imports_extra"] = []
        # imp_ext_unmarshal_kind="none" would normally suppress parseImpExt.
        ctx["imp_ext_unmarshal_kind"] = "none"
        rendered = _render("bidder.go.j2", ctx)
        # Helper present despite imp_ext_unmarshal_kind == "none".
        self.assertIn(
            "func parseImpExt(imp *openrtb2.Imp) (*openrtb_ext.ExtImpAdkernelAdn, error)",
            rendered,
        )
        # dispatchImpressions calls it.
        self.assertIn("impExt, err := parseImpExt(&imps[i])", rendered)

    # ----------------- backward-compat with other branches --------------

    def test_other_batching_kinds_unaffected_by_per_key_ctx(self):
        """F-new-7 EXT-A isolation: when batching_kind != "per-key" the
        per-key branch MUST NOT fire — existing single-batched / per-imp /
        max-imps-per-request branches render unchanged regardless of
        whether `ctx.batching_per_key` is populated (operator may leave
        it set as a no-op for non-per-key bidders)."""
        for kind in ("single-batched", "per-imp", "max-imps-per-request"):
            with self.subTest(kind=kind):
                ctx = self._base_ctx()
                ctx["batching_kind"] = kind
                if kind == "max-imps-per-request":
                    ctx["batching_max_imps"] = 5
                # Leave batching_per_key populated as a no-op.
                rendered = _render("bidder.go.j2", ctx)
                # dispatchImpressions absent.
                self.assertNotIn("func dispatchImpressions", rendered, kind)
                self.assertNotIn("map[openrtb_ext.ExtImpAdkernelAdn][]openrtb2.Imp",
                                 rendered, kind)
                # resolveEndpoint keeps its `*openrtb2.BidRequest` signature.
                self.assertIn(
                    "func (a *adapter) resolveEndpoint(request *openrtb2.BidRequest)",
                    rendered, kind,
                )

    def test_missing_batching_per_key_falls_through_safely(self):
        """F-new-7 EXT-A defensive: when batching_kind="per-key" but
        ctx.batching_per_key is None / absent, the renderer still emits
        a usable shape (helper_name defaults to "dispatchImpressions").
        Operator may set per_key=None during a partial spec assembly and
        the template should not crash."""
        ctx = self._base_ctx()
        ctx["batching_per_key"] = None
        rendered = _render("bidder.go.j2", ctx)
        # Default helper name used.
        self.assertIn("func dispatchImpressions(", rendered)

    # ----------------- compilation gate ---------------------------------

    def test_per_key_template_macro_gofmt_clean(self):
        """F-new-7 EXT-A + F-new-2: full adkernelAdn composition must be
        gofmt-clean. Pinned to catch regressions in the multi-feature
        render path."""
        if shutil.which("gofmt") is None:
            self.skipTest("gofmt not on PATH")
        rendered = _render("bidder.go.j2", self._base_ctx())
        result = subprocess.run(
            ["gofmt", "-e"],
            input=rendered.encode(),
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"gofmt rejected per-key + template-macro render:\n"
            f"stderr={result.stderr.decode()}\n"
            f"rendered={rendered}",
        )

    def test_per_key_static_endpoint_gofmt_clean(self):
        """F-new-7 EXT-A standalone (no F-new-2 composition): per-key
        with a static endpoint must also gofmt-clean. Verifies the
        resolveEndpoint suppression doesn't leave a dangling brace."""
        if shutil.which("gofmt") is None:
            self.skipTest("gofmt not on PATH")
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "static"
        ctx["endpoint_macros"] = None
        ctx["imports_extra"] = []
        rendered = _render("bidder.go.j2", ctx)
        result = subprocess.run(
            ["gofmt", "-e"],
            input=rendered.encode(),
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"gofmt rejected per-key + static render:\n"
            f"stderr={result.stderr.decode()}\n"
            f"rendered={rendered}",
        )


class TestImpIdCorrelation(unittest.TestCase):
    """F-new-7 EXT-B — `bid_type_resolution == "imp-id-correlation"` template
    branch. v1.0.0 promotion blocker.

    Imp-id-correlation classifies a bid by looking up the source imp via
    `bid.ImpID`, inspecting which mediatype field is populated on that imp
    (Banner / Video / Native / Audio), and returning the corresponding
    `openrtb_ext.BidType`. When no matching imp is found OR none of the four
    mediatype fields is populated, the function returns an
    operator-vouched fallback driven by `ctx.bid_type_fallback_value`.

    Master sample: `adapters/adkernelAdn/adkernelAdn.go::getMediaTypeForImpID`
    (D3.8 canary 7 confirmed; upstream returns `BidTypeVideo` as the
    hardcoded miss-fallback).

    Distinction vs. `imp-mediatype-introspection`:
      - imp-mediatype-introspection: terminal miss-fallback is HARDCODED to
        BidTypeBanner.
      - imp-id-correlation: terminal miss-fallback is DRIVEN BY
        `ctx.bid_type_fallback_value` (one of banner / video / audio /
        native). Defaults to "banner" for safe back-compat when omitted.

    ctx schema additions (F-new-7 EXT-B):
      - ctx.bid_type_resolution = "imp-id-correlation"  # new enum value
      - ctx.bid_type_fallback_value: str  # one of {banner,video,audio,native}
                                          # default "banner" when omitted
    """

    # --------------------------- basic emission ----------------------------

    def test_basic_emits_imp_walk_with_video_fallback(self):
        """F-new-7 EXT-B baseline (adkernelAdn shape): the imp-walk loop +
        a terminal fallback driven by ctx.bid_type_fallback_value=video."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        ctx["bid_type_fallback_value"] = "video"
        rendered = _render("bidder.go.j2", ctx)
        # No-error signature (imp-id-correlation has no throw path).
        self.assertIn(
            "func getBidType(bid *openrtb2.Bid, imps []openrtb2.Imp) "
            "openrtb_ext.BidType {",
            rendered,
        )
        # Imp-walk loop — correlate bid → imp by ID.
        self.assertIn("for i := range imps {", rendered)
        self.assertIn("if imps[i].ID == bid.ImpID {", rendered)
        # All four mediatype fields inspected (template covers the canonical
        # union — operator-vouched if their bidder only uses a subset).
        self.assertIn("if imps[i].Banner != nil {", rendered)
        self.assertIn("return openrtb_ext.BidTypeBanner", rendered)
        self.assertIn("if imps[i].Video != nil {", rendered)
        self.assertIn("if imps[i].Native != nil {", rendered)
        self.assertIn("if imps[i].Audio != nil {", rendered)
        # Terminal miss-fallback driven by ctx.bid_type_fallback_value.
        # The walk-fallback `return openrtb_ext.BidTypeVideo` is the LAST
        # return in getBidType.
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        getbidtype_body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(
            getbidtype_body.rstrip().endswith("return openrtb_ext.BidTypeVideo"),
            f"expected getBidType to end with `return openrtb_ext.BidTypeVideo` "
            f"but got:\n{getbidtype_body}",
        )

    # --------------- each fallback variant emits correct return literal ---

    def test_fallback_banner(self):
        """Operator vouches `banner` as the miss-fallback (matches the
        imp-mediatype-introspection hardcoded shape for backward compat)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        ctx["bid_type_fallback_value"] = "banner"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("if imps[i].Banner != nil {", rendered)
        # Last return is the banner fallback.
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(body.rstrip().endswith("return openrtb_ext.BidTypeBanner"))

    def test_fallback_video(self):
        """adkernelAdn-canonical shape: Video miss-fallback."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        ctx["bid_type_fallback_value"] = "video"
        rendered = _render("bidder.go.j2", ctx)
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(body.rstrip().endswith("return openrtb_ext.BidTypeVideo"))

    def test_fallback_native(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        ctx["bid_type_fallback_value"] = "native"
        rendered = _render("bidder.go.j2", ctx)
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(body.rstrip().endswith("return openrtb_ext.BidTypeNative"))

    def test_fallback_audio(self):
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        ctx["bid_type_fallback_value"] = "audio"
        rendered = _render("bidder.go.j2", ctx)
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(body.rstrip().endswith("return openrtb_ext.BidTypeAudio"))

    # ---------------------- defensive / unknown value ----------------------

    def test_missing_fallback_value_defaults_to_banner(self):
        """F-new-7 EXT-B defensive: when ctx.bid_type_fallback_value is None
        / absent, the template defaults to "banner" (preserves the
        imp-mediatype-introspection terminal shape for backward compat).
        Operator gets a usable render rather than a Jinja crash during
        partial spec assembly."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        # bid_type_fallback_value intentionally omitted.
        rendered = _render("bidder.go.j2", ctx)
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(body.rstrip().endswith("return openrtb_ext.BidTypeBanner"))

    def test_unknown_fallback_value_fails_loudly(self):
        """Operator passes a fallback that doesn't exist on the Go side —
        render MUST fail (not silently emit broken Go) so the audit
        notices. Mirrors the constant-type fail-loud pattern."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        ctx["bid_type_fallback_value"] = "other"  # not in
        # {banner,video,audio,native}
        with self.assertRaises(Exception):
            _render("bidder.go.j2", ctx)

    def test_multiformat_imp_only_resolution_fails_loudly(self):
        """Teal #4765 guard: a multiformat-supported adapter cannot resolve bid
        type by imp introspection (fixed priority) — a co-present-format imp
        mis-types every non-first-priority bid. Selecting either imp-only
        resolution while multiformat_supported is true MUST fail loudly at
        render rather than silently emit the mis-typing shape."""
        for resolution in ("imp-mediatype-introspection", "imp-id-correlation"):
            with self.subTest(resolution=resolution):
                ctx = _kobler_bidder_go_ctx()
                ctx["multiformat_supported"] = True
                ctx["bid_type_resolution"] = resolution
                ctx["bid_type_fallback_value"] = "banner"
                with self.assertRaises(Exception):
                    _render("bidder.go.j2", ctx)

    def test_multiformat_by_bid_mtype_renders(self):
        """The correct multiformat shape — by-bid-mtype — renders cleanly and
        emits the bid.MType switch (imp introspection is fallback only)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["multiformat_supported"] = True
        ctx["bid_type_resolution"] = "by-bid-mtype"
        ctx["bid_type_fallback_action"] = "throw"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("switch bid.MType", rendered)

    def test_single_format_imp_introspection_still_renders(self):
        """No regression: a single-format adapter (multiformat_supported unset /
        false) may still resolve by imp introspection — the guard is scoped to
        multiformat adapters only."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-mediatype-introspection"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("func getBidType(", rendered)

    # ------------- composition with full F2 stack -------------------------

    def test_full_f2_composition_adkernelAdn_shape(self):
        """F-new-7 EXT-B composes with F-new-2 (template-macro endpoint),
        F-new-7 EXT-A (per-key batching), AND F-new-34 (naming-form
        resolution) in the canonical adkernelAdn full-feature shape.
        All four features must coexist cleanly in a single render."""
        ctx = {
            "package_name": "adkernelAdn",
            "bidder_class_root": "AdkernelAdn",
            "uses_currency_conversion": False,
            "imp_ext_class_root": "AdkernelAdn",
            "imp_ext_unmarshal_kind": "standard-two-phase",
            # F-new-7 EXT-A: per-key batching
            "batching_kind": "per-key",
            "batching_max_imps": None,
            "batching_per_key": {
                "helper_name": "dispatchImpressions",
                "key_field": "PublisherID",
            },
            # F-new-2: endpoint-template-macro
            "endpoint_resolution_kind": "template-macro",
            "endpoint_macros": [
                {"macro": "PublisherID", "ext_field": "PublisherID",
                 "convert": "itoa"},
            ],
            "http_status_kind": KOBLER_HTTP_STATUS_KIND,
            # F-new-7 EXT-B: imp-id-correlation
            "bid_type_resolution": "imp-id-correlation",
            "bid_type_fallback_value": "video",
            "has_extra_info": False,
            "module_version": GO_MODULE_VERSION,
            "imports_extra": ["strconv"],
            "javadoc_summary": None,
            # F-new-34: naming-form-resolution (mechanical case where forms
            # don't override the legacy keys — purely a composition check).
            "naming_form_resolution": {
                "go_package_name": "adkernelAdn",
                "go_constant_root": "AdkernelAdn",
            },
        }
        rendered = _render("bidder.go.j2", ctx)
        # F-new-2: macros wiring present.
        self.assertIn("text/template", rendered)
        self.assertIn("macros.ResolveMacros", rendered)
        # F-new-7 EXT-A: dispatchImpressions helper + per-batch loop.
        self.assertIn("func dispatchImpressions(", rendered)
        self.assertIn("for key, batchImps := range groups", rendered)
        # F-new-2 + F-new-7 EXT-A composition: resolveEndpoint takes
        # *ExtImp{X}.
        self.assertIn(
            "func (a *adapter) resolveEndpoint(impExt "
            "*openrtb_ext.ExtImpAdkernelAdn) (string, error)",
            rendered,
        )
        # F-new-7 EXT-B: imp-id-correlation getBidType emits.
        self.assertIn("if imps[i].Banner != nil {", rendered)
        self.assertIn("if imps[i].Video != nil {", rendered)
        # Video miss-fallback (operator-vouched per adkernelAdn spec).
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(body.rstrip().endswith("return openrtb_ext.BidTypeVideo"))
        # No-error signature on getBidType (imp-id-correlation has no
        # throw path).
        self.assertIn(
            "func getBidType(bid *openrtb2.Bid, imps []openrtb2.Imp) "
            "openrtb_ext.BidType {",
            rendered,
        )

    # ------------- backward-compat with other bid_type branches -----------

    def test_imp_mediatype_introspection_unchanged(self):
        """F-new-7 EXT-B isolation: the existing
        imp-mediatype-introspection branch MUST render identically to
        pre-EXT-B (terminal fallback HARDCODED to BidTypeBanner; NOT
        driven by ctx.bid_type_fallback_value)."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-mediatype-introspection"
        # Provide bid_type_fallback_value=video — this should be IGNORED
        # by the imp-mediatype-introspection branch (it has a hardcoded
        # banner terminal). Verifies the two branches are truly distinct.
        ctx["bid_type_fallback_value"] = "video"
        rendered = _render("bidder.go.j2", ctx)
        # Existing imp-mediatype-introspection shape: walks Video / Native
        # / Audio BEFORE the inner banner default (so banner imps inside
        # a matching imp-ID fall through to that default).
        self.assertIn("if imps[i].ID == bid.ImpID {", rendered)
        # Banner field check NOT present (imp-mediatype-introspection
        # uses inner default-banner, not an explicit Banner field check).
        # The new imp-id-correlation branch IS the only one that emits
        # `if imps[i].Banner != nil`.
        self.assertNotIn("if imps[i].Banner != nil", rendered)
        # Terminal fallback is hardcoded banner (NOT video, despite
        # bid_type_fallback_value=video).
        getbidtype_start = rendered.index("func getBidType")
        getbidtype_end = rendered.index("\n}\n", getbidtype_start)
        body = rendered[getbidtype_start:getbidtype_end]
        self.assertTrue(body.rstrip().endswith("return openrtb_ext.BidTypeBanner"))

    def test_other_bid_type_branches_unaffected_by_fallback_value(self):
        """F-new-7 EXT-B isolation: when bid_type_resolution is one of the
        non-EXT-B values, the imp-id-correlation imp-walk shape MUST NOT
        leak in (no `if imps[i].Banner != nil` in those renders)."""
        for kind in ("constant-banner", "imp-mediatype-introspection"):
            with self.subTest(kind=kind):
                ctx = _kobler_bidder_go_ctx()
                ctx["bid_type_resolution"] = kind
                rendered = _render("bidder.go.j2", ctx)
                # The Banner-field check is unique to imp-id-correlation.
                self.assertNotIn(
                    "if imps[i].Banner != nil", rendered,
                    f"imp-id-correlation walk leaked into {kind} render",
                )

    # ------------------------- compilation gate ----------------------------

    def test_imp_id_correlation_gofmt_clean(self):
        """F-new-7 EXT-B: the imp-id-correlation render must be
        gofmt-clean. Pinned to catch regressions in the new branch."""
        if shutil.which("gofmt") is None:
            self.skipTest("gofmt not on PATH")
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "imp-id-correlation"
        ctx["bid_type_fallback_value"] = "video"
        rendered = _render("bidder.go.j2", ctx)
        result = subprocess.run(
            ["gofmt", "-e"],
            input=rendered.encode(),
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"gofmt rejected imp-id-correlation render:\n"
            f"stderr={result.stderr.decode()}\n"
            f"rendered={rendered}",
        )

    def test_imp_id_correlation_full_f2_composition_gofmt_clean(self):
        """F-new-7 EXT-B + F-new-7 EXT-A + F-new-2 full composition must
        also be gofmt-clean. Mirrors the per-key composition gate."""
        if shutil.which("gofmt") is None:
            self.skipTest("gofmt not on PATH")
        ctx = {
            "package_name": "adkernelAdn",
            "bidder_class_root": "AdkernelAdn",
            "uses_currency_conversion": False,
            "imp_ext_class_root": "AdkernelAdn",
            "imp_ext_unmarshal_kind": "standard-two-phase",
            "batching_kind": "per-key",
            "batching_max_imps": None,
            "batching_per_key": {
                "helper_name": "dispatchImpressions",
                "key_field": "PublisherID",
            },
            "endpoint_resolution_kind": "template-macro",
            "endpoint_macros": [
                {"macro": "PublisherID", "ext_field": "PublisherID",
                 "convert": "itoa"},
            ],
            "http_status_kind": KOBLER_HTTP_STATUS_KIND,
            "bid_type_resolution": "imp-id-correlation",
            "bid_type_fallback_value": "video",
            "has_extra_info": False,
            "module_version": GO_MODULE_VERSION,
            "imports_extra": ["strconv"],
            "javadoc_summary": None,
        }
        rendered = _render("bidder.go.j2", ctx)
        result = subprocess.run(
            ["gofmt", "-e"],
            input=rendered.encode(),
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"gofmt rejected imp-id-correlation + per-key + "
            f"template-macro render:\n"
            f"stderr={result.stderr.decode()}\n"
            f"rendered={rendered}",
        )


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
        """Defensive: 0-step chain renders without crashing AND emits the
        terminal catchall return (Reviewer H2 correction). Previously the
        function ended without a return statement → Go compile-fail."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = []
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("func getBidType", rendered)
        # H2: terminal catchall return must always be emitted.
        self.assertIn("return openrtb_ext.BidTypeBanner", rendered)

    def test_method_chain_all_next_emits_terminal_catchall(self):
        """H2 regression: chain where every step has fallback_action='next'
        (no terminating throw or return-default) must still emit a terminal
        return at end-of-function. Previously this produced
        'missing return at end of function' Go compile error."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {
                "method": "by-imp-mediatype",
                "fallback_action": "next",
            },
            {
                "method": "by-imp-mediatype",
                "fallback_action": "next",
            },
        ]
        rendered = _render("bidder.go.j2", ctx)
        # The terminal catchall return must follow the chain body.
        # Order check: getBidType { ... terminal-return ... }
        getBidType_start = rendered.index("func getBidType")
        terminal_return = rendered.find("return openrtb_ext.BidTypeBanner", getBidType_start)
        self.assertGreater(terminal_return, getBidType_start,
                           "terminal catchall return missing after method-chain")

    def test_method_chain_mid_chain_throw_does_not_emit_unreachable_code(self):
        """H3 regression: mid-chain step with fallback_action='throw' must
        NOT emit its terminating return (which would make subsequent steps
        unreachable). Only the LAST step's terminating action emits."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {
                "method": "by-imp-mediatype",
                "fallback_action": "throw",  # mid-chain throw — should NOT emit terminating return
            },
            {
                "method": "hardcoded",
                "hardcoded_value": "BidTypeBanner",
                "fallback_action": "return-default",  # last-step terminal return
            },
        ]
        rendered = _render("bidder.go.j2", ctx)
        # Count occurrences of the throw-style error message; should be 0
        # because the second (last) step's fallback_action is return-default.
        # The mid-chain throw should NOT have produced its terminating
        # return either.
        self.assertEqual(
            rendered.count('return "", fmt.Errorf("unable to determine bid type for imp %s"'),
            0,
            "mid-chain throw emitted unreachable terminating return (H3 regression)"
        )

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
    # imp.ext.bidder for the same reason as the exemplary ctx: an adapter that
    # unmarshals imp.Ext unguarded (173 of 215, 80%) returns
    # `failed parsing imp.ext` and the scenario under test never runs.
    request = {
        "id": "test-request-id",
        "imp": [
            {
                "id": "test-imp-id",
                "banner": {"format": [{"w": 300, "h": 250}]},
                "ext": {"bidder": {"test": False}},
            },
        ],
    }
    return {
        "scenario_kind": scenario_kind,
        "http_status_kind": KOBLER_HTTP_STATUS_KIND,
        "mock_bid_request": request,
        "uri": KOBLER_ENDPOINT,
        "expected_request_body": request,
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

    F-new-23 (post-vungle canary v3): the no-response-body scenario
    is gated on `ctx.http_status_kind`. Canonical-helpers adapters
    (vungle/smarthub/etc.) have no nil-body short-circuit and instead
    fall through to `jsonutil.Unmarshal(empty)`, which jsoniter
    answers with `expect { or n, but found <next-byte>`. The fixture
    asserts that error via `comparison: startswith` against the
    `"expect { or n, but found"` prefix (matches upstream flatads
    `response-200-without-body.json`). Default behavior (when
    `http_status_kind` is absent or None) preserves the legacy-raw-go
    kobler shape for back-compat with pre-F-new-23 callers.
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
        """The mockResponse shape does not depend on http_status_kind; only the
        expectations below it do, which is why they are asserted separately in
        the legacy-raw-go and canonical-go-helpers tests."""
        ctx = _supplemental_fixture_ctx("no-response-body")
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        mock = parsed["httpCalls"][0]["mockResponse"]
        self.assertEqual(mock["status"], 200)
        # Body field omitted entirely (matches upstream kobler
        # no-response-body.json — adapterstest delivers Body==nil to the
        # adapter, which kobler-shape adapters short-circuit on).
        self.assertNotIn("body", mock)

    def test_no_response_body_canonical_helpers_expects_the_decode_error(self):
        """A canonical-helpers adapter does not short-circuit an empty 200 body:
        it falls through to jsonutil.Unmarshal and returns `expect { or n, but
        found`. Recognising only the "canonical-helpers" alias here gave such an
        adapter the legacy-raw-go expectations, and the fixture failed with
        `MakeBids had wrong error count. Expected 0, got 1`."""
        for spelling in ("canonical-go-helpers", "canonical-helpers"):
            ctx = _supplemental_fixture_ctx("no-response-body")
            ctx["http_status_kind"] = spelling
            parsed = json.loads(_render("supplemental-fixture.json.j2", ctx))
            self.assertIn("expectedMakeBidsErrors", parsed, spelling)
            self.assertEqual(parsed["expectedMakeBidsErrors"][0]["comparison"],
                             "startswith", spelling)

    def test_no_response_body_legacy_raw_go_unchanged(self):
        """F-new-23: explicit `http_status_kind="legacy-raw-go"` reproduces
        the pre-F-new-23 kobler shape (status 200, no body, no errors,
        empty expectedBidResponses). Pins that the legacy path is
        byte-identical to the existing default."""
        ctx = _supplemental_fixture_ctx("no-response-body")
        ctx["http_status_kind"] = "legacy-raw-go"
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        mock = parsed["httpCalls"][0]["mockResponse"]
        self.assertEqual(mock["status"], 200)
        self.assertNotIn("body", mock)
        # Kobler-shape: no errors, empty expectedBidResponses.
        self.assertNotIn("expectedMakeBidsErrors", parsed)
        self.assertEqual(parsed["expectedBidResponses"], [])

    def test_no_response_body_canonical_helpers_jsonutil_unmarshal_error(self):
        """F-new-23: `http_status_kind="canonical-helpers"` flips the
        no-response-body scenario from kobler-shape (no error) to the
        flatads-shape jsonutil.Unmarshal error. The body-nil case
        falls through to `jsonutil.Unmarshal(empty)`, which jsoniter
        answers with `expect { or n, but found <next-byte>`. Since
        the trailing byte varies (empty/`]`/etc.), the fixture asserts
        the error via `comparison: startswith` against the prefix
        `"expect { or n, but found"`. Matches upstream flatads
        `response-200-without-body.json`."""
        ctx = _supplemental_fixture_ctx("no-response-body")
        ctx["http_status_kind"] = "canonical-helpers"
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        mock = parsed["httpCalls"][0]["mockResponse"]
        # mockResponse shape unchanged: status=200, body omitted.
        self.assertEqual(mock["status"], 200)
        self.assertNotIn("body", mock)
        # expectedBidResponses MUST NOT appear — the canonical-helpers
        # branch surfaces an error rather than a (nil, nil) short-circuit.
        self.assertNotIn("expectedBidResponses", parsed)
        # The error string MUST use startswith comparison against the
        # jsonutil prefix.
        errs = parsed["expectedMakeBidsErrors"]
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]["value"], "expect { or n, but found")
        self.assertEqual(errs[0]["comparison"], "startswith")

    def test_no_response_body_default_http_status_kind_absent(self):
        """F-new-23 backward-compat: when `ctx.http_status_kind` is
        absent OR explicitly None, the template defaults to
        legacy-raw-go (kobler-shape), preserving pre-F-new-23 callers
        verbatim. Pinned for both forms."""
        # Form 1: key absent. The shared ctx now declares http_status_kind so it
        # agrees with the adapter the bidder template emits, so this test drops
        # the key to exercise the pre-F-new-23 caller shape.
        ctx_absent = _supplemental_fixture_ctx("no-response-body")
        ctx_absent.pop("http_status_kind", None)
        rendered_absent = _render("supplemental-fixture.json.j2", ctx_absent)
        parsed_absent = json.loads(rendered_absent)
        self.assertNotIn(
            "expectedMakeBidsErrors", parsed_absent,
            "absent http_status_kind must default to legacy-raw-go (no error)",
        )
        self.assertEqual(parsed_absent["expectedBidResponses"], [])

        # Form 2: key present but None.
        ctx_none = _supplemental_fixture_ctx("no-response-body")
        ctx_none["http_status_kind"] = None
        rendered_none = _render("supplemental-fixture.json.j2", ctx_none)
        parsed_none = json.loads(rendered_none)
        self.assertNotIn(
            "expectedMakeBidsErrors", parsed_none,
            "None http_status_kind must default to legacy-raw-go (no error)",
        )
        self.assertEqual(parsed_none["expectedBidResponses"], [])

        # Both forms must be byte-equal to the explicit "legacy-raw-go"
        # render (the gate is structural, not just expectation-level).
        ctx_explicit = _supplemental_fixture_ctx("no-response-body")
        ctx_explicit["http_status_kind"] = "legacy-raw-go"
        rendered_explicit = _render(
            "supplemental-fixture.json.j2", ctx_explicit
        )
        self.assertEqual(rendered_absent, rendered_explicit)
        self.assertEqual(rendered_none, rendered_explicit)

    def test_other_scenario_kinds_unaffected_by_http_status_kind(self):
        """F-new-23 scope guard: the gate applies ONLY to no-response-body.
        For the other 4 scenario_kind values (status-204/400/404/
        malformed-body), the rendered output MUST be byte-identical
        regardless of http_status_kind."""
        for kind in ("status-204", "status-400", "status-404", "malformed-body"):
            ctx_legacy = _supplemental_fixture_ctx(kind)
            ctx_legacy["http_status_kind"] = "legacy-raw-go"
            ctx_canonical = _supplemental_fixture_ctx(kind)
            ctx_canonical["http_status_kind"] = "canonical-helpers"
            ctx_absent = _supplemental_fixture_ctx(kind)
            r_legacy = _render("supplemental-fixture.json.j2", ctx_legacy)
            r_canonical = _render("supplemental-fixture.json.j2", ctx_canonical)
            r_absent = _render("supplemental-fixture.json.j2", ctx_absent)
            self.assertEqual(
                r_legacy, r_canonical,
                f"http_status_kind must not affect scenario_kind={kind}",
            )
            self.assertEqual(
                r_legacy, r_absent,
                f"absent http_status_kind must equal legacy-raw-go for {kind}",
            )

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

    def test_unknown_scenario_kind_is_a_hard_error(self):
        """This used to render "fail-graceful": an unrecognised kind fell
        through every branch and emitted an empty mockResponse. That is not
        graceful at the point it matters -- adapterstest reads status 0 and
        MakeBids fails with `Unexpected status code: 0. Run with request.debug =
        1 for more info`, which names neither the fixture field nor the bad
        value. The template's own docstring deferred the check to the caller;
        it is enforced here instead."""
        ctx = _supplemental_fixture_ctx("status-200")  # unrecognized
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("supplemental-fixture.json.j2", ctx)
        self.assertIn("ERROR_unknown_scenario_kind", str(cm.exception))

    def test_imp_ids_emit_per_F_new_12(self):
        """F-new-12 (canary v2): adapterstest.RunJSONBidderTest asserts
        non-empty expectedRequest.impIDs. The supplemental template emits
        impIDs when present in ctx (matching exemplary template's guard;
        Reviewer M6 alignment)."""
        ctx = _supplemental_fixture_ctx("status-204")
        ctx["imp_ids"] = ["imp-A", "imp-B"]
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertEqual(
            parsed["httpCalls"][0]["expectedRequest"]["impIDs"],
            ["imp-A", "imp-B"],
        )
        # Render correctness across all 5 known kinds — impIDs always present
        # when supplied.
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

    def test_imp_ids_are_required_not_optional(self):
        """Same hard requirement as the exemplary template -- see
        TestExemplaryFixtureJ2.test_imp_ids_are_required_not_optional. This
        template's Inputs block already documented ctx.imp_ids as "required by
        adapterstest" while emitting it conditionally."""
        ctx = _supplemental_fixture_ctx("status-204")
        ctx.pop("imp_ids", None)
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("supplemental-fixture.json.j2", ctx)
        self.assertIn("ERROR_supplemental_fixture_requires_ctx_imp_ids", str(cm.exception))

    def test_imp_ids_emitted_when_supplied(self):
        parsed = json.loads(_render("supplemental-fixture.json.j2",
                                    _supplemental_fixture_ctx("status-204")))
        self.assertTrue(parsed["httpCalls"][0]["expectedRequest"]["impIDs"])

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
        ctx["uri"] = KOBLER_ENDPOINT
        rendered = _render("supplemental-fixture.json.j2", ctx)
        parsed = json.loads(rendered)
        self.assertEqual(
            parsed["httpCalls"][0]["expectedRequest"]["uri"],
            KOBLER_ENDPOINT,
        )


# ---------------------------------------------------------------------------
# Per-pair ctx helpers for TestRenderedGoCompiles.
#
# Sources (per docs/runs/d3.8-mvp-pairs-spike-2026-05-05.md + each pair's
# canary trace under docs/runs/d3.8-{pair}-canary-*.md):
#   - vungle:        canary v3 § "Pipeline executed" + spike per-pair table
#   - aax:           canary  § Pipeline + § "ctx values" near line 65-69
#   - adverxo:       canary  § Pipeline + § "ctx values" near line 66-70
#   - thetradedesk:  canary  § Pipeline + § "ctx values" near line 68-73
#   - adkernelAdn:   canary  § Pipeline + § "ctx values" near line 77-84
#
# These mirror the ctx the renderer actually wired up at canary time. Where
# the renderer applied an alias-mapping (e.g. thetradedesk's spec value
# `bid-mtype-switch` → ctx value `by-bid-mtype`, F-new-7), the post-mapping
# value is reflected here — i.e. the ctx as the template SEES it, not the
# raw spec value.
# ---------------------------------------------------------------------------


def _vungle_bidder_go_ctx() -> Dict[str, Any]:
    """Vungle canary v3 ctx (B1 constant + B2 currency + B3 custom-headers)."""
    return {
        "package_name": "vungle",
        "bidder_class_root": "Vungle",
        "uses_currency_conversion": True,
        "imp_ext_class_root": "Vungle",
        "imp_ext_unmarshal_kind": "standard-two-phase",
        "batching_kind": "per-imp",
        "batching_max_imps": None,
        "endpoint_resolution_kind": "static",
        "http_status_kind": KOBLER_HTTP_STATUS_KIND,
        "bid_type_resolution": "constant",
        "bid_type_constant": "video",
        "bid_type_fallback_action": "throw",
        "has_extra_info": False,
        "module_version": GO_MODULE_VERSION,
        "imports_extra": [],
        "javadoc_summary": None,
        "custom_headers": [{"name": "X-OpenRTB-Version", "value": "2.6"}],
    }


def _aax_bidder_go_ctx() -> Dict[str, Any]:
    """Aax canary ctx (F-new-1 imp_ext=none + F-new-14 legacy-raw-go +
    method-chain 3-step + Rule 35 has_extra_info=True). Endpoint-kind
    `query-parameter-augmentation` exercises the `else`-TODO branch in
    resolveEndpoint — render compiles (TODO is just a comment + naked
    `return a.endpoint`); this pins current behavior, not desired final
    semantics (F-new-26)."""
    return {
        "package_name": "aax",
        "bidder_class_root": "Aax",
        "uses_currency_conversion": False,
        "imp_ext_class_root": "Aax",
        "imp_ext_unmarshal_kind": "none",
        "batching_kind": "single-batched",
        "batching_max_imps": None,
        "endpoint_resolution_kind": "query-parameter-augmentation",
        "http_status_kind": "legacy-raw-go",
        "legacy_raw_status_handlers": [
            {"status_code": 400, "error_kind": "BadInput"},
        ],
        "bid_type_resolution": "method-chain-fallback",
        "bid_type_method_chain": [
            {"method": "by-bid-ext-typed-field",
             "field": "bid.ext.adCodeType",
             "fallback_action": "next"},
            {"method": "by-imp-mediatype",
             "fallback_action": "next"},
            {"method": "throw"},
        ],
        "has_extra_info": True,
        "module_version": GO_MODULE_VERSION,
        "imports_extra": [],
        "javadoc_summary": None,
    }


def _adverxo_bidder_go_ctx() -> Dict[str, Any]:
    """Adverxo canary ctx (B1 by-bid-mtype throw + B2 currency +
    multi-token-substitution endpoint TODO). The `multi-token-substitution`
    endpoint kind falls to the template's TODO-stub branch which still
    returns `a.endpoint` — gofmt parses it; this pins CURRENT BEHAVIOR
    (compile-clean stub), not the eventual macro-resolution emission
    (F-new-26)."""
    return {
        "package_name": "adverxo",
        "bidder_class_root": "Adverxo",
        "uses_currency_conversion": True,
        "imp_ext_class_root": "Adverxo",
        "imp_ext_unmarshal_kind": "standard-two-phase",
        "batching_kind": "per-imp",
        "batching_max_imps": None,
        "endpoint_resolution_kind": "multi-token-substitution",
        "http_status_kind": KOBLER_HTTP_STATUS_KIND,
        "bid_type_resolution": "by-bid-mtype",
        "bid_type_fallback_action": "throw",
        "has_extra_info": False,
        "module_version": GO_MODULE_VERSION,
        "imports_extra": [],
        "javadoc_summary": None,
    }


def _thetradedesk_bidder_go_ctx() -> Dict[str, Any]:
    """TheTradeDesk canary ctx (F-new-7 bid-mtype-switch alias +
    template-macro endpoint TODO + F-new-31 has_extra_info=False
    workaround). `bid_type_resolution` is the renderer-mapped value
    `by-bid-mtype` (not the raw spec value `bid-mtype-switch`).
    `has_extra_info=False` is a renderer-side workaround for the
    empty-extraInfo-struct TODO emission — pins current behavior."""
    return {
        "package_name": "thetradedesk",
        "bidder_class_root": "TheTradeDesk",
        "uses_currency_conversion": False,
        "imp_ext_class_root": "TheTradeDesk",
        "imp_ext_unmarshal_kind": "standard-two-phase",
        "batching_kind": "single-batched",
        "batching_max_imps": None,
        "endpoint_resolution_kind": "template-macro",
        "http_status_kind": KOBLER_HTTP_STATUS_KIND,
        "bid_type_resolution": "by-bid-mtype",
        "bid_type_fallback_action": "throw",
        "has_extra_info": False,
        "module_version": GO_MODULE_VERSION,
        "imports_extra": [],
        "javadoc_summary": None,
    }


def _adkerneladn_bidder_go_ctx() -> Dict[str, Any]:
    """AdkernelAdn canary ctx (per-key→single-batched workaround +
    imp-id-correlation→by-bid-mtype workaround + template-macro TODO +
    custom_headers Java-canonical mixed-case). Pins current renderer
    behavior; the raw spec uses `per-key` batching and
    `imp-id-correlation` bid-type, neither of which the template
    supports — F-new-7 EXT-A and EXT-B."""
    return {
        "package_name": "adkerneladn",
        "bidder_class_root": "AdkernelAdn",
        "uses_currency_conversion": False,
        "imp_ext_class_root": "AdkernelAdn",
        "imp_ext_unmarshal_kind": "standard-two-phase",
        "batching_kind": "single-batched",
        "batching_max_imps": None,
        "endpoint_resolution_kind": "template-macro",
        "http_status_kind": KOBLER_HTTP_STATUS_KIND,
        "bid_type_resolution": "by-bid-mtype",
        "bid_type_fallback_action": "return-default",
        "bid_type_fallback_value": "banner",
        "has_extra_info": False,
        "module_version": GO_MODULE_VERSION,
        "imports_extra": [],
        "javadoc_summary": None,
        "custom_headers": [{"name": "X-OpenRTB-Version", "value": "2.5"}],
    }


class TestRenderedGoCompiles(unittest.TestCase):
    """Verify that rendered Go source actually parses via `gofmt -e`.

    Reviewer L1 architectural fix: previous H2/H3/H4/H6 escapes show that
    nothing in the test pipeline invoked Go tooling against rendered
    output. A template can pass Jinja rendering AND every existing
    substring-presence test yet still produce Go source `gofmt`/`go vet`/
    `go build` reject. This class plugs that gap with a universal
    parse-time check and 4 targeted regressions for the reviewer's HIGH
    findings.

    Skip behavior: if `gofmt` is not on PATH (CI environments without a
    Go toolchain), every test in this class is skipped via
    `setUpClass`. The skip leaves the rest of the suite green; a
    Go-equipped CI run picks the checks up.

    Scope intentionally limited to `gofmt -e`: parses Go source without
    needing module context. `go vet`/`go build` would catch additional
    semantic bugs (e.g. unreachable-code H3) but require a working
    GOPATH/module — out of scope here. See module docstring for how to
    add those gated behind an opt-in env var.
    """

    @classmethod
    def setUpClass(cls):
        if shutil.which("gofmt") is None:
            raise unittest.SkipTest(
                "gofmt not on PATH; skipping rendered-Go compile tests"
            )

    def _gofmt_check(self, rendered: str, file_label: str) -> None:
        """Run `gofmt -e` against rendered source; assert exit 0.

        On non-zero, fails the test with a message including gofmt's
        stderr and the rendered source — operators reading the failure
        immediately see what syntax broke."""
        result = subprocess.run(
            ["gofmt", "-e"],
            input=rendered.encode(),
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                f"gofmt rejected rendered {file_label} (exit={result.returncode}):\n"
                f"--- stderr ---\n{result.stderr.decode()}\n"
                f"--- rendered ---\n{rendered}"
            )

    # ----- Per-pair MVP shape compile checks -------------------------------

    def test_kobler_shape_compiles(self):
        rendered = _render("bidder.go.j2", _kobler_bidder_go_ctx())
        self._gofmt_check(rendered, "kobler bidder.go")

    def test_vungle_shape_compiles(self):
        rendered = _render("bidder.go.j2", _vungle_bidder_go_ctx())
        self._gofmt_check(rendered, "vungle bidder.go")

    def test_aax_shape_compiles(self):
        rendered = _render("bidder.go.j2", _aax_bidder_go_ctx())
        self._gofmt_check(rendered, "aax bidder.go")

    def test_adverxo_shape_compiles(self):
        rendered = _render("bidder.go.j2", _adverxo_bidder_go_ctx())
        self._gofmt_check(rendered, "adverxo bidder.go")

    def test_thetradedesk_shape_compiles(self):
        rendered = _render("bidder.go.j2", _thetradedesk_bidder_go_ctx())
        self._gofmt_check(rendered, "thetradedesk bidder.go")

    def test_adkerneladn_shape_compiles(self):
        rendered = _render("bidder.go.j2", _adkerneladn_bidder_go_ctx())
        self._gofmt_check(rendered, "adkernelAdn bidder.go")

    # ----- Reviewer HIGH-finding regressions -------------------------------

    def test_h2_method_chain_all_next_compiles(self):
        """H2 regression: chain with all-`next` steps must compile (prior
        bug: 'missing return at end of function'). Reviewer's H2 was
        fixed via the terminal-catchall return at end of getBidType — this
        test pins that the rendered Go actually parses."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {"method": "by-imp-mediatype", "fallback_action": "next"},
            {"method": "by-imp-mediatype", "fallback_action": "next"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        self._gofmt_check(rendered, "method-chain all-next bidder.go")

    def test_h3_method_chain_mid_chain_throw_compiles(self):
        """H3 regression: chain with mid-chain throw + later steps must
        parse via gofmt (prior bug: unreachable-code emit). gofmt -e
        only guarantees parse-cleanness; semantic unreachable detection
        is `go vet`'s job (out of scope here, see class docstring), but
        a parse failure here would indicate a regression in the
        terminating-return suppression logic."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "method-chain-fallback"
        ctx["bid_type_method_chain"] = [
            {"method": "by-imp-mediatype", "fallback_action": "throw"},
            {"method": "hardcoded", "hardcoded_value": "BidTypeBanner",
             "fallback_action": "return-default"},
        ]
        rendered = _render("bidder.go.j2", ctx)
        self._gofmt_check(rendered, "method-chain mid-chain-throw bidder.go")

    def test_h4_simulator_output_no_empty_string_keys(self):
        """H4 regression: `simulate_makerequests_mutations` with
        `device-zero-fields` must DELETE the named keys (not assign
        empty strings). The rendered exemplary-fixture JSON's
        mockBidRequest.device must NOT contain `"ip": ""` — Go's
        omitempty marshaling deletes empty fields, so a fixture with
        `"ip": ""` would byte-mismatch the actual emitted body."""
        # Late import to avoid hard-coupling this test file's import
        # graph to scripts.lib.port_engine when port_engine is absent
        # (this test is the only consumer of simulate_makerequests_mutations
        # in this test file).
        from scripts.lib.port_engine import simulate_makerequests_mutations

        mock = {
            "id": "r1",
            "device": {"ip": "1.2.3.4", "ipv6": "::1", "ua": "Mozilla/5.0"},
            "imp": [{"id": "imp-1",
                     "banner": {"format": [{"w": 300, "h": 250}]}}],
        }
        mutated = simulate_makerequests_mutations(mock, [
            {"kind": "device-zero-fields", "fields": ["ip", "ipv6"]},
        ])
        # Direct assertion on simulator output — H4's contract is
        # at the simulator wire-form, BEFORE the fixture template.
        self.assertNotIn(
            "ip", mutated["device"],
            "device-zero-fields must delete `ip`, not assign empty string",
        )
        self.assertNotIn(
            "ipv6", mutated["device"],
            "device-zero-fields must delete `ipv6`, not assign empty string",
        )

        # Render through exemplary-fixture.json.j2 with the mutated
        # body; the rendered JSON must also not contain `"ip": ""`.
        ctx = _kobler_exemplary_fixture_ctx()
        ctx["mock_bid_request"] = mutated
        rendered = _render("exemplary-fixture.json.j2", ctx)
        # Substring check on the wire form — the only way `ip` could
        # appear in device after the simulator deleted it would be if
        # the fixture template re-introduced it.
        self.assertNotIn(
            '"ip": ""', rendered,
            'rendered fixture must not contain `"ip": ""` (H4 wire-form check)',
        )
        self.assertNotIn(
            '"ipv6": ""', rendered,
            'rendered fixture must not contain `"ipv6": ""` (H4 wire-form check)',
        )
        # And confirm the rendered JSON is parse-clean (sanity).
        parsed = json.loads(rendered)
        self.assertNotIn("ip", parsed["mockBidRequest"]["device"])
        self.assertNotIn("ipv6", parsed["mockBidRequest"]["device"])
        # Other device fields preserved end-to-end.
        self.assertEqual(parsed["mockBidRequest"]["device"]["ua"], "Mozilla/5.0")

    def test_h6_orphan_enum_value_falls_through_to_todo(self):
        """H6 regression: an unrecognized `bid_type_resolution` value
        (such as a previously-supported enum that was removed during
        consolidation, e.g. `ext-prebid-video-placement`) must hit the
        catchall `else` branch — emit a TODO comment AND a banner default
        return — so the rendered Go still compiles. Pins that adding new
        bid-type kinds or removing old ones doesn't accidentally crash
        the template OR emit invalid Go."""
        ctx = _kobler_bidder_go_ctx()
        ctx["bid_type_resolution"] = "ext-prebid-video-placement"
        rendered = _render("bidder.go.j2", ctx)
        # TODO comment fires.
        self.assertIn(
            "TODO[port-java2go]: bid_type_resolution=ext-prebid-video-placement",
            rendered,
            "orphan bid_type_resolution must emit TODO catchall comment",
        )
        # Banner default emitted.
        self.assertIn(
            "return openrtb_ext.BidTypeBanner",
            rendered,
            "orphan bid_type_resolution must emit banner default return",
        )
        # And the rendered Go parses.
        self._gofmt_check(rendered, "orphan-enum bidder.go")

    # ----- Optional bonus: imp-ext-pojo also gofmt-clean ------------------

    def test_imp_ext_pojo_compiles(self):
        """imp-ext-pojo.go.j2 emits to the openrtb_ext package — this
        is the cross-package POJO every adapter parsing imp.ext.bidder
        relies on. Render the kobler shape and gofmt-check."""
        rendered = _render("imp-ext-pojo.go.j2", _kobler_imp_ext_pojo_ctx())
        self._gofmt_check(rendered, "kobler imp-ext-pojo.go")


class TestNamingFormResolution(unittest.TestCase):
    """F-new-34 — `ctx.naming_form_resolution` Rule 46 multi-form ctx schema.

    When ctx.naming_form_resolution is provided, the per-aspect forms win
    over legacy ctx.package_name + ctx.imp_ext_class_root keys. When
    absent, the legacy single-form keys flow through unchanged
    (backward-compatible with pre-F-new-34 ctx shape).

    The 6 affected pairs in the v1.0.0 set: adkernelAdn, thetradedesk,
    audienceNetwork, cadent_aperture_mx, stroeerCore, sspBC. Tests verify
    that the rendered Go output picks up the Go-side forms (yaml /
    package / constant root) correctly for at least 2 representative
    cases.
    """

    def _base_ctx(self) -> Dict[str, Any]:
        return {
            "package_name": "PLACEHOLDER_PKG",
            "bidder_class_root": "PLACEHOLDER_ROOT",
            "uses_currency_conversion": False,
            "imp_ext_class_root": None,  # intentional: drive from forms dict.
            "imp_ext_unmarshal_kind": "standard-two-phase",
            "batching_kind": "single-batched",
            "batching_max_imps": None,
            "endpoint_resolution_kind": "static",
            "http_status_kind": KOBLER_HTTP_STATUS_KIND,
            "bid_type_resolution": "imp-mediatype-introspection",
            "has_extra_info": False,
            "module_version": GO_MODULE_VERSION,
            "imports_extra": [],
            "javadoc_summary": None,
        }

    def test_adkerneladn_forms_emit_camelcase_package(self):
        """adkernelAdn master sample: package + EndpointTemplate name +
        ExtImp class all derive from the forms sub-map's camelCase /
        PascalCase forms (NOT the lowercase legacy ctx.package_name)."""
        ctx = self._base_ctx()
        ctx["endpoint_resolution_kind"] = "template-macro"
        ctx["endpoint_macros"] = [
            {"macro": "PublisherID", "ext_field": "PublisherID", "convert": "itoa"},
        ]
        ctx["imports_extra"] = ["strconv"]
        ctx["naming_form_resolution"] = {
            "go_yaml_name": "adkernelAdn",
            "go_package_name": "adkernelAdn",
            "go_constant_root": "AdkernelAdn",
            "java_yaml_name": "adkerneladn",
            "java_class_root": "AdkernelAdn",
            "java_package": "adkerneladn",
        }
        rendered = _render("bidder.go.j2", ctx)
        # Go package directive uses the camelCase form.
        self.assertIn("package adkernelAdn", rendered)
        self.assertNotIn("package PLACEHOLDER_PKG", rendered)
        # EndpointTemplate name is prefixed with the camelCase form.
        self.assertIn(
            'template.New("adkernelAdnEndpointTemplate").Parse(cfg.Endpoint)',
            rendered,
        )
        # ExtImp class derives from go_constant_root (PascalCase).
        self.assertIn("openrtb_ext.ExtImpAdkernelAdn", rendered)
        # The lowercase Java form does NOT leak into the Go output.
        self.assertNotIn("openrtb_ext.ExtImpAdkerneladn", rendered)
        self.assertNotIn("package adkerneladn", rendered)

    def test_thetradedesk_forms_preserve_brand_capital(self):
        """thetradedesk: package is lowercase `thetradedesk`, but the
        constant root preserves the PascalCase brand `TheTradeDesk`. The
        ExtImp class must use the constant-root form."""
        ctx = self._base_ctx()
        ctx["naming_form_resolution"] = {
            "go_yaml_name": "thetradedesk",
            "go_package_name": "thetradedesk",
            "go_constant_root": "TheTradeDesk",
            "java_yaml_name": "thetradedesk",
            "java_class_root": "TheTradeDesk",
            "java_package": "thetradedesk",
        }
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("package thetradedesk", rendered)
        # PascalCase brand preserved in the Go type ref.
        self.assertIn("openrtb_ext.ExtImpTheTradeDesk", rendered)
        # The naive-pascalcase form (`Thetradedesk`) does NOT appear.
        self.assertNotIn("openrtb_ext.ExtImpThetradedesk", rendered)

    def test_cadent_aperture_mx_package_drops_underscores(self):
        """cadent_aperture_mx: directory keeps underscores
        (`go_yaml_name`) but the `package X` directive drops them
        (`go_package_name == cadentaperturemx`). Pin that the template
        emits the underscore-stripped form for the package directive."""
        ctx = self._base_ctx()
        ctx["naming_form_resolution"] = {
            "go_yaml_name": "cadent_aperture_mx",
            "go_package_name": "cadentaperturemx",
            "go_constant_root": "CadentApertureMX",
            "java_yaml_name": "emxdigital",
            "java_class_root": "EmxDigital",
            "java_package": "emxdigital",
        }
        rendered = _render("bidder.go.j2", ctx)
        # Package directive is the underscore-stripped form.
        self.assertIn("package cadentaperturemx", rendered)
        # The directory form (with underscores) MUST NOT appear as the
        # package directive (Go would reject it as an identifier).
        self.assertNotIn("package cadent_aperture_mx", rendered)
        # And the ExtImp class is the constant root, preserving the brand acronym.
        self.assertIn("openrtb_ext.ExtImpCadentApertureMX", rendered)

    def test_legacy_ctx_keys_pass_through_when_forms_absent(self):
        """Backward-compat: when naming_form_resolution is absent or None,
        the legacy ctx.package_name + ctx.imp_ext_class_root keys flow
        through unchanged. This is the pre-F-new-34 ctx shape — the 265
        mechanical bidders use this path."""
        ctx = self._base_ctx()
        ctx["package_name"] = "kobler"
        ctx["imp_ext_class_root"] = "Kobler"
        # naming_form_resolution explicitly absent.
        self.assertNotIn("naming_form_resolution", ctx)
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("package kobler", rendered)
        self.assertIn("openrtb_ext.ExtImpKobler", rendered)

    def test_explicit_imp_ext_class_root_wins_over_forms(self):
        """Escape hatch: when ctx.imp_ext_class_root is explicitly set,
        it wins over the forms dict's go_constant_root. Covers the rare
        bidder whose ExtImp class root diverges from its constant root."""
        ctx = self._base_ctx()
        ctx["imp_ext_class_root"] = "ExplicitOverride"
        ctx["naming_form_resolution"] = {
            "go_yaml_name": "kobler",
            "go_package_name": "kobler",
            "go_constant_root": "Kobler",
            "java_yaml_name": "kobler",
            "java_class_root": "Kobler",
            "java_package": "kobler",
        }
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("openrtb_ext.ExtImpExplicitOverride", rendered)
        # The forms-derived constant root must NOT win.
        self.assertNotIn("openrtb_ext.ExtImpKobler", rendered)

    def test_forms_go_package_name_wins_over_legacy_package_name(self):
        """When BOTH naming_form_resolution.go_package_name AND
        ctx.package_name are set, the forms dict's go_package_name wins
        for the `package` directive. This test scopes to the
        package-directive interaction; imp_ext_class_root is also set
        to a stale value but NOT asserted here (escape-hatch behavior
        — ctx.imp_ext_class_root explicit wins over forms — is covered
        by test_explicit_imp_ext_class_root_wins_over_forms below)."""
        ctx = self._base_ctx()
        ctx["package_name"] = "stale_legacy_value"
        # imp_ext_class_root deliberately set; the escape-hatch contract is
        # NOT tested here (the package directive is the assertion target).
        # See test_explicit_imp_ext_class_root_wins_over_forms for the
        # complementary case that asserts ExtImp{X} survives.
        ctx["imp_ext_class_root"] = "StaleRoot"
        ctx["naming_form_resolution"] = {
            "go_yaml_name": "adkernelAdn",
            "go_package_name": "adkernelAdn",
            "go_constant_root": "AdkernelAdn",
            "java_yaml_name": "adkerneladn",
            "java_class_root": "AdkernelAdn",
            "java_package": "adkerneladn",
        }
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("package adkernelAdn", rendered)
        self.assertNotIn("package stale_legacy_value", rendered)


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




class TestEmittedGoAdapterRunsUnderAdapterstest(unittest.TestCase):
    """Defects found by running the emitted adapter under adapterstest.

    `go build` and `go vet` had been run against the emitted Go; the fixture-driven
    harness had not. Emitting bidder.go.j2 + bidder-test.go.j2 + params-test.go.j2
    with one exemplary and five supplemental fixtures into prebid-server at
    0ba35231 and running `go test` surfaced four separate reasons the emitted
    adapter could not pass its own emitted fixtures. All four now pass:
    TestJsonSamples, TestValidParams, TestInvalidParams, 6 fixtures, gofmt and vet
    clean.
    """

    def test_builder_endpoint_comes_from_the_spec_not_a_placeholder(self):
        """RunJSONBidderTest builds the adapter with the test file's endpoint and
        then compares the request it produced against each fixture's
        expectedRequest.uri. The template hardcoded "https://test.example.com/bid",
        so every emitted adapter failed with `httpRequest[0].uri ... does not match
        expected`. 241 of the 247 upstream adapters that have both a Builder
        endpoint and exemplary uris match (97%); of the 6 that do not, two pass a
        deliberately invalid endpoint and one leaves macros unexpanded."""
        rendered = _render("bidder-test.go.j2", _kobler_bidder_test_ctx())
        self.assertIn(KOBLER_ENDPOINT, rendered)
        self.assertNotIn("test.example.com", rendered)

    def test_builder_endpoint_is_required(self):
        ctx = _kobler_bidder_test_ctx()
        ctx.pop("endpoint", None)
        with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
            _render("bidder-test.go.j2", ctx)
        self.assertIn("ERROR_bidder_test_requires_ctx_endpoint", str(cm.exception))

    def test_every_fixture_context_agrees_on_the_endpoint(self):
        """Three contexts feed one run: the Builder endpoint, the exemplary
        fixture's uri and the supplemental fixture's uri. A placeholder in any one
        of them fails the run, so they read one constant."""
        self.assertEqual(_kobler_bidder_test_ctx()["endpoint"], KOBLER_ENDPOINT)
        for call in _kobler_exemplary_fixture_ctx()["http_calls"]:
            self.assertEqual(call["uri"], KOBLER_ENDPOINT)
        self.assertEqual(_supplemental_fixture_ctx("status-204")["uri"], KOBLER_ENDPOINT)

    def test_fixture_imps_carry_ext_bidder(self):
        """173 of the 215 upstream adapters that unmarshal imp.Ext do it unguarded
        (80%), and the emitted adapter is in that group, so an imp without
        ext.bidder makes MakeRequests return `failed parsing imp.ext` before the
        scenario under test runs. 1369 of 1413 upstream exemplary fixtures with an
        imp carry ext.bidder (96%)."""
        for ctx in (_kobler_exemplary_fixture_ctx(),
                    _supplemental_fixture_ctx("status-204")):
            for imp in ctx["mock_bid_request"]["imp"]:
                self.assertIn("bidder", imp.get("ext") or {},
                              "every fixture imp needs ext.bidder")

    def test_expected_request_body_is_not_a_stub(self):
        """The emitted kobler-shape adapter forwards the request unmodified. A
        stub expected body reports `Expected RequestData was not returned by
        adapters' MakeRequests() implementation` against a correct adapter."""
        ctx = _kobler_exemplary_fixture_ctx()
        self.assertEqual(ctx["http_calls"][0]["body"], ctx["mock_bid_request"])

    def test_fixture_currency_is_set_by_the_mock_response(self):
        """bidder.go.j2 assigns bidderResponse.Currency = bidResponse.Cur
        unguarded, which is the corpus norm (101 of 141, 71%), so it overwrites
        the "USD" that NewBidderResponse seeds. A fixture that asserts a currency
        its mock response never sets fails with `Got , expected USD`; 290 of the
        515 exemplary fixtures belonging to those 101 adapters set `cur` to match
        (56%) and 214 assert no currency (41%)."""
        ctx = _kobler_exemplary_fixture_ctx()
        expected = ctx["expected_currency"]
        curs = {c["response"].get("cur") for c in ctx["http_calls"]
                if isinstance(c.get("response"), dict)}
        self.assertIn(expected, curs,
                      "the asserted currency must be one the mock response sets")

    def test_canonical_helpers_branch_accepts_the_taxonomy_spelling(self):
        """behavior-taxonomy.md spells the helper case `canonical-go-helpers`, and
        that is what a source spec's code.make_bids.http_status_handling.kind
        carries -- 11 of the golden specs declare it. The template tested only the
        historical `canonical-helpers` alias, so passing the spec value through
        fell to raw status checks: the pattern Rule 30 tells a Java-to-Go porter
        NOT to emit, for the one value that means "use the helpers"."""
        for spelling in ("canonical-go-helpers", "canonical-helpers"):
            ctx = _kobler_bidder_go_ctx()
            ctx["http_status_kind"] = spelling
            rendered = _render("bidder.go.j2", ctx)
            self.assertIn("adapters.IsResponseStatusCodeNoContent", rendered, spelling)
            self.assertIn("adapters.CheckResponseStatusCodeForErrors", rendered, spelling)

    def test_unknown_http_status_kind_is_a_hard_error(self):
        """Falling through to raw checks on an unrecognised value is how the
        alias mismatch above stayed invisible. `legacy-raw` was documented in the
        Inputs block and consumed by no branch."""
        for bad in ("legacy-raw", "canonical", "typo"):
            ctx = _kobler_bidder_go_ctx()
            ctx["http_status_kind"] = bad
            with self.assertRaises(jinja2.exceptions.UndefinedError) as cm:
                _render("bidder.go.j2", ctx)
            self.assertIn("ERROR_unknown_http_status_kind", str(cm.exception), bad)

    def test_absent_http_status_kind_still_renders(self):
        """Pre-F-new-23 callers did not pass the field; absence stays supported
        and keeps the raw-check shape."""
        ctx = _kobler_bidder_go_ctx()
        ctx["http_status_kind"] = None
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("responseData.StatusCode", rendered)
        self.assertNotIn("adapters.IsResponseStatusCodeNoContent", rendered)

    def test_bidder_and_fixture_templates_normalise_the_kind_identically(self):
        """The fixture's expectations must match the adapter that was emitted. If
        only one template recognises a spelling, the pair is incoherent and the
        no-response-body fixture fails with `MakeBids had wrong error count`."""
        for spelling in ("canonical-go-helpers", "canonical-helpers"):
            bctx = _kobler_bidder_go_ctx(); bctx["http_status_kind"] = spelling
            uses_helpers = "adapters.IsResponseStatusCodeNoContent" in _render("bidder.go.j2", bctx)
            fctx = _supplemental_fixture_ctx("no-response-body")
            fctx["http_status_kind"] = spelling
            expects_decode_error = "expectedMakeBidsErrors" in json.loads(
                _render("supplemental-fixture.json.j2", fctx))
            self.assertEqual(uses_helpers, expects_decode_error, spelling)


class TestEmittedGoCompilesCleanly(unittest.TestCase):
    """Two defects found by handing the emitted Go to a compiler.

    Neither was reachable by reading the template or by asserting on rendered
    substrings, which is why both survived until `go build` and `go vet` ran.
    """

    def test_no_unreachable_return_after_a_terminating_chain(self):
        """`go vet` reports `unreachable code`, and upstream gates on it:
        `validate.sh` runs `go vet ./...` and both CI workflows invoke
        `validate.sh`. So this is a build failure upstream, not a style nit.

        The terminal catchall after the method-chain walker was emitted
        unconditionally. When the chain's last step already returns -- method
        `throw`/`hardcoded`, or fallback_action `throw`/`return-default` -- the
        result was two consecutive returns with the second dead. aax is the
        corpus case: its chain ends in a throw.
        """
        rendered = _render("bidder.go.j2", _aax_bidder_go_ctx())
        body = rendered[rendered.index("func getBidType"):] if "func getBidType" in rendered else rendered
        # the error return must not be immediately followed by another return
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        for i, line in enumerate(lines[:-1]):
            if line.startswith("return ") and lines[i + 1].startswith("return "):
                self.fail(f"two consecutive returns -- `go vet` calls the second "
                          f"unreachable:\n    {line}\n    {lines[i + 1]}")

    def test_chain_without_a_terminating_step_still_gets_a_catchall(self):
        """The other direction: the catchall exists so a chain whose every step
        falls through still compiles. Removing it entirely would trade
        `unreachable code` for `missing return at end of function`."""
        ctx = _aax_bidder_go_ctx()
        chain = ctx.get("bid_type_method_chain") or ctx.get("bid_type_chain")
        if not chain:
            self.skipTest("this ctx does not carry an inspectable method chain")
        for step in chain:
            if isinstance(step, dict):
                step["fallback_action"] = "next"
                if step.get("method") in ("throw", "hardcoded"):
                    step["method"] = "imp-id-correlation"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("return openrtb_ext.BidType", rendered,
                      "a fully falling-through chain must still end in a return")

    def test_imp_ext_type_name_is_not_hardcoded_to_the_ExtImp_prefix(self):
        """Upstream Go uses two conventions for the imp-ext struct. Measured at
        prebid-server 0ba35231 over openrtb_ext/imp_*.go: 170 `ExtImp{Bidder}`
        and 78 `ImpExt{Bidder}`, so the minority form is 31% of the corpus --
        `ImpExtAdverxo`, `ImpExtVungle` against `ExtImpKobler`. Hardcoding one
        prefix emits a type name that disagrees with the vendor's existing Go
        file for roughly a third of bidders."""
        ctx = _adverxo_bidder_go_ctx()
        ctx["imp_ext_type_name"] = "ImpExtAdverxo"
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("openrtb_ext.ImpExtAdverxo", rendered)
        self.assertNotIn("openrtb_ext.ExtImpAdverxo", rendered)

    def test_imp_ext_type_name_defaults_to_the_majority_form(self):
        ctx = _adverxo_bidder_go_ctx()
        ctx.pop("imp_ext_type_name", None)
        rendered = _render("bidder.go.j2", ctx)
        self.assertIn("openrtb_ext.ExtImp", rendered)

    def test_pojo_template_honours_the_same_type_name(self):
        """The POJO and the bidder must agree, or the emitted pair does not
        compile against each other."""
        ctx = _kobler_imp_ext_pojo_ctx()
        ctx["imp_ext_type_name"] = "ImpExtKobler"
        rendered = _render("imp-ext-pojo.go.j2", ctx)
        self.assertIn("type ImpExtKobler struct {", rendered)

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
