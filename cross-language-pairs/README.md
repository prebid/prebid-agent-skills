# Cross-language assertion pairs

Per-bidder dual-spec assertion files. Each file declares which fields of an Adapter Specification MUST match across the Go and Java sides, which MAY legitimately diverge, and what severity to attach to each divergence.

## Files

| Bidder | Go fixture | Java fixture | Notable assertions |
|---|---|---|---|
| `152media` | yes | yes | `bidder_params_sha256` byte-only divergence; `gvl_vendor_id` semantic divergence (Go alias override 1111 vs Java parent inherit 14) |
| `aax` | **no** (Java-only) | yes | Java omits `minLength: 1` on `cid` and `crid` — port-fidelity bug; `severity: fail` (only `fail` in suite) |
| `appnexus` | yes | yes | Java adds `json-aliases-present` to `combinators_used`; mediafuse declared as parent_alias on Java only |
| `elementaltv` | **no** (Java-only) | yes | Three-step rename from Adoppler |
| `kobler` | yes | yes | Canonical clean reference; both sides byte-equal `bidder_params_sha256` |
| `mediasquare` | yes | yes | `Bidder<MediasquareRequest>` parameterized request type; site-capabilities omitted on Java |
| `optidigital` | yes | yes | `default_enabled` differs (Go true, Java false) |

The two orphan pairs (`aax`, `elementaltv`) have no Go-side fixtures yet. The current CI harness skips assertions for orphans (Phase D follow-up: author the missing Go fixtures so the `severity: fail` assertions actually fire).

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

Consumed at runtime by `scripts/round-trip-ci.py` rule R5. As of PR #1, the harness reads four of sixteen assertion keys (`bidder_params_sha256`, `bidder_info_capabilities`, `bidder_info_gvl_vendor_id`, `params_schema_interpretation`); Phase D work expands consumption to the rest.

## Adding a new pair

1. Author Go and Java fixtures at `prebid-server-{go,java}/read/test-fixtures/{bidder}.golden.spec.yaml`.
2. Author the dual-spec assertion file with field-by-field expectations grounded in real upstream behavior.
3. Run `python3 scripts/round-trip-ci.py` to verify.
4. Add a row to the table above.
