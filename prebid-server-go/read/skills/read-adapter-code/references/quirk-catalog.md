# Quirk Catalog

The closed registry of `edge_case_taxon` values from [../../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry](../../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry), indexed by when this skill emits them. Each entry: when to emit, real-adapter example with `path:line` citation, what spec field cannot capture the pattern (so quirks aren't a dumping ground), and the `edge_case_taxon` value to use.

The taxonomy is the source-of-truth list. This catalog is the **read-time emission decision matrix**: it tells `read-adapter-code` how to detect each pattern in adapter Go code or test fixtures and which spec field surface drives the quirk.

A quirk entry is structured as:

```yaml
- id: <unique-within-spec-id>
  file: <relative-path-from-repo-root>
  summary: <one-sentence-free-text>
  edge_case_taxon: <enum-from-registry>
```

Every `custom` value in any enumerated behavioral field REQUIRES a paired quirk (Validation Rule R3). The `edge_case_taxon` MUST be one of the registered values in [`../../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry`](../../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry); readers that emit an unregistered taxon fail validation.

---

## Taxon coverage owned by this skill

This skill emits quirks under these taxa (the others are emitted by sibling skills — see the "Owner" column):

| Taxon | Owner | Surfaces in (this skill) |
|---|---|---|
| `hardcoded-config-as-anti-pattern` | this skill | adapter source quirks |
| `json-key-style-mismatch` | shared (this skill emits when observed in test/adapter source); `read-bidder-params` emits `notes` on the field | adapter quirks (text mention) |
| `port-fidelity-divergence` | shared (this skill records the Go-side aspect; the Java-source spec records the Java-side aspect) | this skill does NOT typically emit; orchestrator merges |
| `bidder-constant-mismatch` | this skill (test-side) + `read-bidder-params` (params_test.go side) | adapter test quirks; `provenance.warnings` |
| `yaml-field-name-typo` | `read-bidder-info` | not emitted by this skill |
| `multi-file-layout-justified` | this skill | adapter quirks |
| `legacy-go-pattern-pre-1.22` | this skill | adapter quirks |
| `identifier-rule-workaround` | Java side (n/a in Go) | not emitted by this skill |
| `acronym-case-preservation` | Java side (n/a in Go) | not emitted by this skill |
| `tilde-alias-syntax` | `read-bidder-info` (when porting Java specs) | not emitted by this skill |
| `bidder-rename-three-step` | `read-bidder-info` | not emitted by this skill |
| `endpoint-compression-typo` | `read-bidder-info` | not emitted by this skill |
| `currency-conversion-bidrequest-context` | Java-source spec only | not emitted by this skill |
| `mutation-idiom-tobuilder` | Java-source spec only | not emitted by this skill |
| `dev-endpoint-config-promotion` | Java-source spec only (cross-language win) | not emitted by this skill |
| `incomplete-classification` | this skill | adapter quirks |
| `legacy-encoding-json-direct-usage` | this skill | adapter quirks; `provenance.warnings` |
| `legacy-test-helpers-imported` | this skill | adapter quirks; `provenance.warnings` |
| `unguarded-currency-overwrite` | this skill | adapter quirks |
| `hardcoded-bid-type` | this skill | adapter quirks |
| `legacy-impext-naming` | shared (this skill flags the file-side observation; `read-bidder-params` flags the type-name) | adapter quirks |

Java-only taxa (`identifier-rule-workaround, acronym-case-preservation, tilde-alias-syntax, bidder-rename-three-step, currency-conversion-bidrequest-context, mutation-idiom-tobuilder, dev-endpoint-config-promotion`) are NOT emitted by this skill — they appear only in Java-source specs.

---

## Catalog entries (this skill's owned taxa)

### `hardcoded-config-as-anti-pattern`

**Description**: Adapter hardcodes a value that should live in YAML config (`extra_info`) or a YAML field.
**When to emit**: Whenever this skill detects a literal endpoint URL, region map, secret key, or per-imp behavior toggle that is a Go package-level `const` or hardcoded literal.
**What spec field cannot capture it**: `code.adapter_struct.fields[]` records the struct fields but NOT the hardcoded constants; `bidder_info.endpoint_construction.kind: dev-prod-toggle` captures the BEHAVIOR but not the anti-pattern.
**Real-adapter example**: `adapters/kobler/kobler.go:23` — `const devBidderEndpoint = "https://bid-service.dev.essrtb.com/bid/prebid_server_rtb_call"`. Should live in YAML `extra_info` or be promoted to a typed YAML field (which the Java port did via `KoblerConfigurationProperties.devEndpoint`).

```yaml
- id: hardcoded-dev-endpoint
  file: kobler.go
  summary: "devBidderEndpoint is a const literal in source rather than ExtraAdapterInfo or YAML field. Anti-pattern."
  edge_case_taxon: hardcoded-config-as-anti-pattern
```

A second sub-case from kobler: per-imp toggle behavior reading `imp.ext.bidder.test` from only the FIRST imp (`kobler.go:55` — `i == 0` branch). Multi-imp callers cannot toggle dev endpoint per-imp:

```yaml
- id: dev-prod-toggle-via-imp-ext-test-flag
  file: kobler.go
  summary: "testMode flag pulled from imp.ext.bidder.test of the FIRST imp only (line 55, i==0); other imps' test flags are ignored."
  edge_case_taxon: hardcoded-config-as-anti-pattern
```

### `json-key-style-mismatch`

**Description**: JSON tag uses a different style than surrounding adapter (e.g., `pubclick` instead of `pub_click`).
**When to emit**: When this skill observes the adapter's outgoing payload constructing a JSON tag that does not match the publisher-facing imp ext struct's tag for the same field. Cross-file consistency check.
**What spec field cannot capture it**: `params.ext_struct.fields[].json_tag` records the publisher-facing tag (owned by `read-bidder-params`); a divergence between adapter outgoing and ext struct is a quirk-only observation.
**Real-adapter example**: `adapters/msft/msft.go` — outgoing payload uses `pubclick`, while `openrtb_ext/imp_msft.go` declares `json:"pub_click"` (the field reviewers added in PR #4592). Adapter source uses the legacy form because Microsoft's spec accepts both.

```yaml
- id: pubclick-vs-pub_click-mismatch
  file: adapters/msft/msft.go
  summary: "Adapter outgoing payload uses pubclick (Microsoft legacy); openrtb_ext/imp_msft.go declares pub_click (canonical). Both accepted by Microsoft spec."
  edge_case_taxon: json-key-style-mismatch
```

### `bidder-constant-mismatch` (test-side)

**Description**: Test runner calls `Builder()` (or `validator.Validate()`) with the wrong `openrtb_ext.Bidder*` constant — typically a copy-paste artifact from another adapter.
**When to emit**: This skill detects a mismatch between the constant referenced in the test file and the canonical `openrtb_ext.Bidder{Xyz}` for this adapter. The mismatch passes tests because the framework does not cross-check the constant.
**What spec field cannot capture it**: `params.params_test.bidder_constant_referenced` (owned by `read-bidder-params`) records the constant but does NOT distinguish it from `bidder_constant`; the skill computes the mismatch and emits both a quirk and a `provenance.warnings` entry per Validation Rule R7.
**Real-adapter examples**:
- `adapters/kobler/kobler_test.go:12` — `Builder(openrtb_ext.BidderKargo, ...)` (copy-paste from Kargo adapter).
- `adapters/kobler/params_test.go:47` — `validator.Validate(openrtb_ext.BidderKrushmedia, ...)` (copy-paste from Krushmedia).

```yaml
- id: bidder-constant-mismatch-test
  file: adapters/kobler/kobler_test.go
  summary: "kobler_test.go calls Builder with openrtb_ext.BidderKargo (copy-paste from another adapter)"
  edge_case_taxon: bidder-constant-mismatch
- id: bidder-constant-mismatch-params-test
  file: adapters/kobler/params_test.go
  summary: "params_test.go TestInvalidParams calls validator.Validate with openrtb_ext.BidderKrushmedia (copy-paste from another adapter); TestValidParams uses BidderKobler correctly"
  edge_case_taxon: bidder-constant-mismatch
```

The companion `provenance.warnings` entry has `type: bidder-constant-mismatch` with `file:line` citation per [../../shared/adapter-spec.schema.json](../../shared/adapter-spec.schema.json) (`$defs/Provenance.warnings`).

### `multi-file-layout-justified`

**Description**: Multi-file Go layout that the heuristic flags but is justified by the adapter's complexity (custom request body, large helpers, etc.).
**When to emit**: When `code.file_layout.kind: multi-file` AND the additional non-test files exist for a structural reason (a custom `*Request`/`*Response` type, an IAB category data table, a bidder-keywords parser).
**What spec field cannot capture it**: `code.file_layout.kind: multi-file` records the existence; the quirk records the justification (which downstream porters need).
**Real-adapter examples**:
- `adapters/mediasquare/` — `mediasquare.go` + `models.go`. `models.go` defines `msqParameters` and `msqResponse` (non-OpenRTB shape). Justified by `code.make_requests.request_body.kind: custom`.
- `adapters/msft/iab_categories.go` — generated lookup table (large). Justified by `code.iab_category_storage.storage_kind: go-data-table`.
- `adapters/appnexus/models.go` — keywords parser with custom UnmarshalJSON. Justified by `cross_language.port_concerns.custom_unmarshaljson_present: true`.

```yaml
- id: mediasquare-models-split
  file: adapters/mediasquare/structs.go
  summary: "Custom request/response types live in models.go because mediasquare uses a non-OpenRTB request body (codes[] array)."
  edge_case_taxon: multi-file-layout-justified
```

### `legacy-go-pattern-pre-1.22`

**Description**: Go code uses a pattern that pre-dates Go 1.22 (capture-by-reference loops, exported adapter struct, legacy `usersync.go` file).
**When to emit**: When this skill observes specific legacy idioms.
**What spec field cannot capture it**: The structural fields (`code.adapter_struct.type_visibility: exported`) record the shape; the quirk explains why this is legacy.
**Real-adapter examples**:
- `adapters/33across/33across.go` — `type TtxAdapter struct` (exported struct identifier; pre-canonical).
- `adapters/<old>/usersync.go` — the legacy user-sync file (most modern adapters do not have this; user-sync URL is in YAML).

```yaml
- id: ttx-exported-adapter-struct
  file: adapters/33across/33across.go
  summary: "TtxAdapter is exported (capital T) — pre-canonical pattern. New adapters use unexported `adapter`."
  edge_case_taxon: legacy-go-pattern-pre-1.22
```

### `incomplete-classification`

**Description**: Reader could not classify a behavioral field with affirmative evidence.
**When to emit**: This skill detects a code shape that does not affirmatively match any enum value. Default-emission rule (per [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md) point 1): an enumerated field's default is emitted only when structural evidence affirmatively matches the default. Absence of evidence emits no value AND requires an `incomplete-classification` quirk.
**What spec field cannot capture it**: The enumerated field would be set to `custom`; the quirk explains what the reader saw.
**Real-adapter example**: when an adapter's `MakeBids` does not contain any of the canonical bid type resolution shapes (no MType switch, no imp lookup, no ext field check), this skill emits `bid_type_resolution.method_chain: [{ method: custom }]` plus an `incomplete-classification` quirk.

```yaml
- id: bid-type-resolution-incomplete
  file: adapters/{xyz}/{xyz}.go
  summary: "MakeBids returns bids without a recognizable bid-type resolution path. Manual review required."
  edge_case_taxon: incomplete-classification
```

This is the read-time analog of the review skill's "manual review" recommendation. The orchestrator MAY surface this in the Markdown summary as a "needs human attention" callout.

### `legacy-encoding-json-direct-usage`

**Description**: Go adapter uses `encoding/json` `Marshal`/`Unmarshal` directly instead of `jsonutil`.
**When to emit**: This skill detects `encoding/json.Marshal` or `encoding/json.Unmarshal` calls in adapter source AND `imports.has_jsonutil: false`.
**What spec field cannot capture it**: `imports.has_jsonutil: false` is a presence flag; the quirk records the specific call sites and recommends migration to `jsonutil`.
**Real-adapter example**: legacy adapters predating the `jsonutil` package (most have been migrated by v4.1.0; check via grep for `json.Marshal(` excluding `json.RawMessage`).

```yaml
- id: legacy-encoding-json
  file: adapters/{xyz}/{xyz}.go
  summary: "Adapter calls json.Marshal at line N and json.Unmarshal at line M. Recommended migration: jsonutil.Marshal / jsonutil.Unmarshal."
  edge_case_taxon: legacy-encoding-json-direct-usage
```

Companion `provenance.warnings` entry per Validation Rule R9 in [../../shared/adapter-spec.md#validation-rules-r1-r10](../../shared/adapter-spec.md#validation-rules-r1-r10).

### `legacy-test-helpers-imported`

**Description**: Adapter test imports `OrtbMockService`, `BidOnTags`, `SampleBid`, or `VerifyStringValue` from `adapterstest/adapter_test_util.go` — should migrate to JSON harness.
**When to emit**: This skill detects any of these imports in `_test.go` files for the adapter. The auxiliary helpers are documented as not used by `RunJSONBidderTest` at [../../../../review/skills/shared/framework-utilities.md#test-harness-contract](../../../../review/skills/shared/framework-utilities.md#test-harness-contract).
**What spec field cannot capture it**: `tests.uses_canonical_harness: false` flags the absence of `RunJSONBidderTest`, but the quirk pinpoints the specific legacy helpers.
**Real-adapter example**: older `adapters/cadent_aperture_mx/` test pre-migration.

```yaml
- id: legacy-test-helpers
  file: adapters/cadent_aperture_mx/cadent_test.go
  summary: "Test imports adapterstest.OrtbMockService and BidOnTags. Recommended migration: replace Go unit tests with JSON fixtures via RunJSONBidderTest."
  edge_case_taxon: legacy-test-helpers-imported
```

Companion `provenance.warnings` entry per Validation Rule R10.

### `unguarded-currency-overwrite`

**Description**: Adapter sets `bidResponse.Currency = response.Cur` without guarding against empty string.
**When to emit**: This skill detects `bidResponse.Currency = response.Cur` (or equivalent) with NO surrounding `if response.Cur != ""` check.
**What spec field cannot capture it**: `code.make_bids.currency_overwrite_safety: unguarded` records the classification; the quirk pinpoints the file and line.
**Real-adapter example**: `adapters/optidigital/optidigital.go` — `bidResponse.Currency = response.Cur` directly. Per [../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md#currency-overwrite-hazard](../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md#currency-overwrite-hazard), this overwrites the default `"USD"` with empty string when the bidder returns an empty currency.

```yaml
- id: unguarded-currency-overwrite
  file: optidigital.go
  summary: "bidResponse.Currency = response.Cur is unguarded — overwrites default USD with empty string if response.Cur is empty."
  edge_case_taxon: unguarded-currency-overwrite
```

### `hardcoded-bid-type`

**Description**: `MakeBids` returns a fixed `BidType` regardless of upstream response.
**When to emit**: This skill detects `bid_type_resolution.method_chain` with a single step `{ method: hardcoded, hardcoded_value: <type> }`.
**What spec field cannot capture it**: `bid_type_resolution.method_chain[]` records the structure; the quirk documents the anti-pattern (skipping imp validation).
**Real-adapter example**: `adapters/optidigital/optidigital.go` — always returns `openrtb_ext.BidTypeBanner` for every bid, even though the imp could in principle declare other media types. Reviewers tolerate this only for genuinely single-mediatype adapters.

```yaml
- id: hardcoded-banner-bid-type
  file: optidigital.go
  summary: "MakeBids hardcodes BidTypeBanner for every bid; cannot return non-banner even if server replied with one."
  edge_case_taxon: hardcoded-bid-type
```

### `legacy-impext-naming`

**Description**: Imp ext struct uses legacy `ImpExt{Bidder}` pattern instead of canonical `ExtImp{Bidder}`.
**When to emit**: This skill observes the adapter source referencing `openrtb_ext.ImpExt{Xyz}` instead of `openrtb_ext.ExtImp{Xyz}`. The struct name itself lives in `params.ext_struct.type_name` (owned by `read-bidder-params`); this skill flags the file-side observation when the adapter source uses the legacy name.
**What spec field cannot capture it**: `params.ext_struct.type_name` records the struct name (read-bidder-params); the quirk surfaces the cross-file consistency observation.
**Real-adapter example**: `openrtb_ext/imp_optidigital.go` — `type ImpExtOptidigital struct` (legacy). Canonical convention is `ExtImpOptidigital`.

```yaml
- id: legacy-impext-naming
  file: openrtb_ext/imp_optidigital.go
  summary: "Uses legacy ImpExt{Bidder} naming pattern (ImpExtOptidigital). Canonical convention is ExtImp{Bidder}."
  edge_case_taxon: legacy-impext-naming
```

---

## Sibling-skill taxa (NOT emitted by this skill, listed for cross-reference)

These taxa are documented for completeness — `read-adapter-code` does NOT emit them. The orchestrator merges quirks from all skills before emitting the spec.

### `port-fidelity-divergence`

Owner: shared (Java-source spec emits the destination-side observation; Go-source spec emits the source-side aspect via `cross_language.go_specific_concerns[]`). Java port differs from Go source in load-bearing way (canonical: Kobler currency-conversion bidRequest context).

### `yaml-field-name-typo` / `endpoint-compression-typo`

Owner: `read-bidder-info`. YAML field uses a near-canonical name PBS silently ignores. Canonical: Ogury `endpointCompression` vs `endpoint-compression`.

### `tilde-alias-syntax` / `bidder-rename-three-step`

Owner: `read-bidder-info`. Java-side YAML aliases declared as `oldname: ~` rather than full block, or bidder rename via DELETE old YAML + CREATE new YAML + alias-back via tilde.

### `currency-conversion-bidrequest-context` / `mutation-idiom-tobuilder` / `dev-endpoint-config-promotion`

Owner: Java-source spec only. Cross-language port concerns flagged on the Java side.

### `identifier-rule-workaround` / `acronym-case-preservation`

Owner: Java-source spec only. Canonical: `152media` → `OneFiveTwoMediaTest` class; `ElementalTV`, `FeedAd`, `BidTheatre`.

---

## Decision flow for emitting a quirk

When this skill encounters a pattern:

1. Does the pattern map to an enumerated field's `custom` value? If yes, emit a quirk (REQUIRED by Validation Rule R3).
2. Does the pattern match a registered taxon's "When to emit" criterion above? If yes, emit a quirk.
3. Does the pattern match a known structural anti-pattern but the field already captures the BEHAVIOR? Emit a quirk only when the anti-pattern needs porter awareness (canonical: `hardcoded-bid-type`, `unguarded-currency-overwrite`).
4. Otherwise, do NOT emit a quirk. The taxonomy is closed; new patterns require a registry update at [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md) before use.

A quirk's `id` SHOULD be globally unique within the spec; conventional format: `<short-pattern>-<adapter>-<location>` (e.g., `hardcoded-dev-endpoint`, `bidder-constant-mismatch-test`). The orchestrator deduplicates `id` collisions across skills.

A quirk's `file` SHOULD be the path relative to the repository root (e.g., `adapters/kobler/kobler.go`) when the observation is at the file level; some quirks cite a directory (`adapters/mediasquare/`) when the observation is structural across multiple files.

---

## Sources

- Closed registry of taxa: [../../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry](../../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry).
- `prebid/prebid-server` master at v4.1.0 (commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` as of 2026-04-27):
  - `adapters/kobler/kobler.go:23` — hardcoded `devBidderEndpoint` const.
  - `adapters/kobler/kobler.go:55` — per-imp `i == 0` branch reading `imp.ext.bidder.test`.
  - `adapters/kobler/kobler_test.go:12` — Builder called with `BidderKargo`.
  - `adapters/kobler/params_test.go:47` — Validate called with `BidderKrushmedia`.
  - `adapters/optidigital/optidigital.go` — unguarded `bidResponse.Currency = response.Cur`; hardcoded `BidTypeBanner`.
  - `openrtb_ext/imp_optidigital.go` — `ImpExtOptidigital` legacy naming.
  - `adapters/33across/33across.go` — exported `TtxAdapter` struct.
  - `adapters/mediasquare/structs.go` — custom `msqParameters`/`msqResponse` types.
  - `adapters/msft/iab_categories.go` — generated lookup table.
  - `adapters/msft/msft.go` — `pubclick` outgoing JSON tag.
  - `openrtb_ext/imp_msft.go` — `pub_click` ext-struct JSON tag.
  - `adapters/appnexus/models.go` — custom UnmarshalJSON.
- Validation rules R3, R7, R9, R10: [../../shared/adapter-spec.md#validation-rules-r1-r10](../../shared/adapter-spec.md#validation-rules-r1-r10).
- Default emission rule: [../../shared/behavior-taxonomy.md#how-to-read-this-taxonomy](../../shared/behavior-taxonomy.md#how-to-read-this-taxonomy).
- Currency overwrite hazard cross-reference: [../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md#currency-overwrite-hazard](../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md#currency-overwrite-hazard).
- Test harness contract cross-reference: [../../../../review/skills/shared/framework-utilities.md#test-harness-contract](../../../../review/skills/shared/framework-utilities.md#test-harness-contract).
- Companion file: [adapter-code-patterns.md](adapter-code-patterns.md) — the structural classification rules.
- Companion file: [file-role-heuristics.md](file-role-heuristics.md) — file role mapping.
