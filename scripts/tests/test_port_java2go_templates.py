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
        rendered = _render("bidder-info.yaml.j2", _kobler_bidder_info_ctx())
        # Camel-case names should appear.
        self.assertIn("endpointCompression", rendered)
        self.assertIn("gvlVendorID", rendered)
        # Kebab-case (Java side) should NOT appear.
        self.assertNotIn("endpoint-compression", rendered)
        self.assertNotIn("gvl-vendor-id", rendered)

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
        self.assertIn("func TestKobler(t *testing.T) {", rendered)
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
