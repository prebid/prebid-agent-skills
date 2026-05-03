# Cross-language assertion pairs

Per-bidder dual-spec assertion files. Each file declares which fields of an Adapter Specification MUST match across the Go and Java sides, which MAY legitimately diverge, and what severity to attach to each divergence.

## Files

| Bidder | Go fixture | Java fixture | Notable assertions |
|---|---|---|---|
| `152media` | yes | yes | `bidder_params_sha256` byte-only divergence; `gvl_vendor_id` semantic divergence (Go alias override 1111 vs Java parent inherit 14) |
| `aax` | yes | yes | Java omits `minLength: 1` on `cid` and `crid` — port-fidelity bug; `severity: fail` (only `fail` in suite) |
| `adkernelAdn` | yes | yes | Rule 46 master sample (Go `adkernelAdn` camelCase ↔ Java `adkerneladn` lowercase); macro-form asymmetry across multiple URL params |
| `adverxo` | yes | yes | Macro-form asymmetry (Go template `{{.X}}` ↔ Java plain `{{X}}` resolved via String.replace) |
| `appnexus` | yes | yes | Java adds `json-aliases-present` to `combinators_used`; mediafuse declared as parent_alias on Java only |
| `elementaltv` | yes | yes | Three-step rename from Adoppler; `lifecycle.rename` master sample |
| `emxdigital` (paired Go: `cadent_aperture_mx`) | yes | yes | ADR-006 dual-core registration (Go has BOTH `cadent_aperture_mx` and `emx_digital` registered as core bidders sharing one Builder); Java retains `emxdigital` (legacy EMX brand) as canonical parent |
| `freewheelssp` | yes | yes | ADR-007 F2 master sample (`language_stamped_headers[]`: `Componentid: prebid-go` ↔ `prebid-java`); Go also carries `aliasOf:` stub for `freewheel-ssp` |
| `kobler` | yes | yes | Canonical clean reference; both sides byte-equal `bidder_params_sha256` |
| `limelightDigital` | yes | yes | Alias-empire master (3 children each side) |
| `mediasquare` | yes | yes | `Bidder<MediasquareRequest>` parameterized request type; site-capabilities omitted on Java |
| `optidigital` | yes | yes | `default_enabled` differs (Go true, Java false) |
| `smarthub` | yes | yes | Alias-empire parent-canonical case (Attekmi rebrand); macro-form asymmetry |
| `teqblaze` | yes | yes | White-label-only-parent case (10 aliases each side); parent uses placeholder endpoint |
| `thetradedesk` | yes | yes | ADR-007 F4 master sample (`bid_post_processing.macros[]` AUCTION_PRICE replacement in `bid.NURL`/`bid.AdM`/`bid.BURL`) |
| `vungle` | yes | yes | ADR-007 F3 master sample (`entity_strategies.Site: replace-with-app-synthesis`, `App: synthesize-app-replacement`); bilateral lifecycle rename (liftoff→vungle) |

All 16 pairs have both Go and Java fixtures. The `aax` `severity: fail` assertion is gated via `.github/known-broken-pairs.txt` so the harness reports it as informational rather than blocking — fix is upstream Java-side (add `minLength: 1` to `static/bidder-params/aax.json`).

## Schema (informal)

Each file:

```yaml
bidder_name: <name>
go_spec: <path-to-go-fixture | null>
java_spec: <path-to-java-fixture | null>

assertions:
  bidder_params_sha256:
    equivalent: bool
    byte_equal: bool
    severity: pass | warn | fail
    divergence_kind: none | byte-only | semantic | divergent-semantic
    divergence_summary: "..."
  bidder_info_capabilities:
    ...
  # Plus: bidder_info_default_enabled, bidder_info_endpoint,
  # bidder_info_endpoint_compression, bidder_info_endpoint_construction,
  # bidder_info_geoscope, bidder_info_gvl_vendor_id, bidder_info_maintainer,
  # bidder_info_modifying_vast_xml_allowed, alias_metadata,
  # lifecycle_rename, params_schema_interpretation, port_lineage,
  # reviewer_cohort, test_fixture_cost.

overall:
  cross_language_state: byte-equal | byte-only-divergent | divergent-semantic
  blocker_count: int
  warning_count: int
  notes: ["..."]
```

Consumed at runtime by `scripts/round-trip-ci.py` rule R5. The harness reads the strict-keys list at `R5_STRICT_KEYS` (semantic-equivalence-required: `bidder_info.capabilities`, `params.schema_interpretation.{required_fields, combinators_used, flexible_types}`, `bidder_info.{gvl_vendor_id, endpoint_compression, geoscope, maintainer, modifying_vast_xml_allowed}`) and the divergent-keys list at `R5_DIVERGENT_KEYS` (legitimate-language-idiom-divergence: `bidder_info.{endpoint, endpoint_construction, default_enabled}`, `meta.alias_metadata`). Phase D port skills will consume the remaining R5-DIVERGENT keys (`lifecycle_rename`, `port_lineage`, `reviewer_cohort`, `test_fixture_cost`).

## Adding a new pair

1. Author Go and Java fixtures at `prebid-server-{go,java}/read/test-fixtures/{bidder}.golden.spec.yaml`.
2. Author the dual-spec assertion file with field-by-field expectations grounded in real upstream behavior.
3. Run `python3 scripts/round-trip-ci.py` to verify.
4. Add a row to the table above.
