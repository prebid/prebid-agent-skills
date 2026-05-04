---
name: read-adapter-code
description: Extracts the `code:` and `tests:` fragments of an Adapter Specification from prebid-server-go adapter source. USE WHEN the orchestrator dispatches read-time analysis for `adapters/{xyz}/*.go` (excluding `params_test.go`) and `adapters/{xyz}/{xyz}test/**/*.json`. Owns Go file inventory, role classification, package/Builder/MakeRequests/MakeBids behavior extraction, fixture inventory across the 5 known subdirs, and `quirks[]` emission for unclassifiable patterns.
version: 1.0.0
---

# read-adapter-code (Go)

This skill is the heaviest of the four Go read-skills. It walks every `.go` file in `adapters/{xyz}/` (excluding `params_test.go`, owned by `read-bidder-params`) plus every JSON fixture under `adapters/{xyz}/{xyz}test/**/`, classifies each by role, extracts behavioral evidence, and emits the `code:`, `tests:`, and Go-specific cross-language fragments of the canonical Adapter Specification (see [../shared/adapter-spec.md](../shared/adapter-spec.md)).

The skill operates in read mode against a single resolved commit — the orchestrator hands it pre-fetched file paths and the resolved SHA. It produces deterministic output: re-running on the same commit yields a fragment idempotent under round-trip (Validation Rule R4: `yaml.safe_load → safe_dump` is byte-stable). Byte-identical reproduction modulo `provenance.read.timestamp_utc` is the target; R4 enforces idempotency.

## What this skill produces

It owns these top-level spec keys:

- `code.*` — the entire `code` block (package_or_class, file_layout, imports, adapter_struct, builder, make_requests, make_bids).
- `tests.*` — the entire `tests` block excluding `unit_test_*` / `test_application_properties_*` fields (which are Java-only).
- `cross_language.go_artifacts.*` — Go-side path hints (densely populated).
- `cross_language.java_artifacts.*` — Java-side path hint stubs (sparse — this skill does not read Java).
- `cross_language.go_specific_concerns[]` — free-text Go-only port-fidelity concerns (densely populated).
- `cross_language.java_specific_concerns[]` — empty list on Go-source specs.
- `cross_language.port_concerns.{multi_file_layout, package_directory_mismatch, custom_unmarshaljson_present, mutation_idiom_divergence}` — booleans this skill computes.
- `quirks[]` — entries whose evidence lives in adapter Go code or test fixtures.
- `headers_constructed.*` — when `MakeRequests` constructs headers explicitly (the orchestrator merges authentication metadata from `read-bidder-info` if applicable).

It does **not** own (defer to sibling skills): `bidder_info.*` (read-bidder-info), `bidder_params_json` / `params.*` (read-bidder-params), `meta.*` and `provenance.*` (orchestrator), `spring_config` / `bidder_class` / `iab_category_storage.{yaml-inlined fields}` (Java-only — null on Go specs).

## Inputs from the orchestrator

```yaml
inputs:
  bidder_name: kobler                          # The {xyz} slug.
  resolved_commit: SHA                         # Frozen commit.
  fetch_method: github-raw | local-checkout | gh-cli
  files:                                       # Pre-discovered paths owned by this skill.
    go_files:
      - adapters/kobler/kobler.go
      - adapters/kobler/kobler_test.go
    test_fixtures:
      exemplary: [adapters/kobler/koblertest/exemplary/site-simple_banner.json, ...]
      supplemental: [...]
      amp: []
      video: []
      videosupplemental: []
  fixture_mode: count-only | summary | verbatim
```

The orchestrator excludes `params_test.go` from `go_files` per `read-bidder-params` ownership (see [shared/adapter-spec.schema.json](../shared/adapter-spec.schema.json) `$defs/Code` and `$defs/Params`). If `params_test.go` appears in the input, this skill skips it silently.

## Workflow

### Step 1 — Inventory `.go` files

For each path in `inputs.files.go_files`:

1. Read the file at `provenance.source.resolved_commit` (orchestrator-provided; do not re-fetch).
2. Compute `loc` (line count, including blank lines and the final newline if present).
3. Skip the file if it is `params_test.go` (defensive — orchestrator should have already excluded it).
4. Tag the file with a single `role` per the rule table in [references/file-role-heuristics.md](references/file-role-heuristics.md).

Record the inventory as `code.file_layout.files[]`. Set `code.file_layout.kind: multi-file` if `len(files) > 1` (counting only non-test `.go` files — `_test.go` does not count toward multi-file layout); otherwise `single-file`.

### Step 2 — Classify each file by role

Use [references/file-role-heuristics.md](references/file-role-heuristics.md) for the deterministic rule order. Roles in the spec enum (closed 6-value set): `implementation, types, parsers, utils, models, data-table`. Test files (`_test.go`) are filtered out earlier by the orchestrator and do NOT appear in `code.file_layout.files[]`; the test-fixture inventory lives under `tests.fixture_inventory.*` instead. There is no `tests`, `params-tests`, or `usersync` role — those file kinds are accounted for in the test inventory and `bidder_info.user_sync` blocks respectively.

Multi-file detection is rare (mediasquare, msft, appnexus). When detected, set `cross_language.port_concerns.multi_file_layout: true`.

### Step 3 — Extract `code.package_or_class`, `directory_name`, `package_directory_mismatch`

1. From the implementation file (role=`implementation`), parse the `package` clause. The token after `package` is `code.package_or_class`.
2. The directory segment of the file's path is `code.directory_name`.
3. Set `package_directory_mismatch: true` when the two differ. Canonical case: `33across/` directory containing `package ttx`. The orchestrator additionally emits a `package-directory-mismatch` warning under `provenance.warnings` (Validation Rule R6).

### Step 4 — Extract `code.imports.*` (helpers presence flags)

Parse the `import (...)` block of the implementation file. Populate booleans:

| Spec field | Trigger import paths |
|---|---|
| `imports.has_template_engine` | `text/template` OR `github.com/prebid/prebid-server/v4/macros` (when `macros.NewStringIndexBasedReplacer` is invoked). |
| `imports.has_currency_helper` | Adapter calls `reqInfo.ConvertCurrency(...)` anywhere in the file (presence of method call, not just import). |
| `imports.has_jsonutil` | `github.com/prebid/prebid-server/v4/util/jsonutil`. If absent AND `encoding/json.Marshal`/`Unmarshal` is invoked, emit a `legacy-encoding-json-direct-usage` quirk and a `provenance.warnings` entry (Validation Rule R9). |
| `imports.third_party[]` | Any import path NOT under `github.com/prebid/prebid-server/v4/` and NOT a Go stdlib package. List each import alias-and-path. |

The full helper registry (canonical helpers, `errortypes.*`, `macros.EndpointTemplateParams` 18 fields, `jsonutil.*` extras) lives at [../../../review/skills/shared/framework-utilities.md](../../../review/skills/shared/framework-utilities.md). Do not re-list helpers here.

### Step 5 — Extract `code.adapter_struct.*`

Locate the type declaration for the adapter struct (typically `type adapter struct { ... }`).

1. `type_name` — the identifier (e.g., `adapter`, `TtxAdapter`, `adkernelAdapter`). See [references/adapter-code-patterns.md](references/adapter-code-patterns.md#adapter-struct-shapes) for the three observed shapes.
2. `type_visibility` — `unexported` if first letter is lowercase, `exported` otherwise.
3. `fields[]` — each declared field as `{ name, type }`. Pointer types record as `*Type`.

### Step 6 — Extract `code.builder.*`

Locate the `Builder(bidderName ..., config config.Adapter, server config.Server) (adapters.Bidder, error)` function. Apply [references/adapter-code-patterns.md](references/adapter-code-patterns.md#builder-canonical-signature) classification:

- `signature_canonical: true` if the parameter list matches the canonical signature exactly.
- `extra_adapter_info_used: true` if the body references `config.ExtraAdapterInfo`.
- `template_parsed_at_build: true` if the body parses a `text/template` (signal: `template.New(...).Parse(config.Endpoint)` or `macros.NewStringIndexBasedReplacer()` invocation).
- `errors_returned[]` — categorize each non-nil error path: `url_parse_error`, `template_parse_error`, `extra_info_unmarshal_error`, `validation_error`, or a free-text taxon. Empty list when Builder cannot fail (kobler, optidigital pattern).

### Step 7 — Classify `code.make_requests.*`

Locate `func (a [*]adapter) MakeRequests(...)`. Apply rules from [../shared/behavior-taxonomy.md](../shared/behavior-taxonomy.md) and [references/adapter-code-patterns.md](references/adapter-code-patterns.md#makerequests-classification):

1. **`batching.rules[]`** — ordered list. Default `[{ kind: single-batched }]` when one `RequestData` is returned with `len(request.Imp)` imps. Other rule kinds (`per-imp, max-imps-per-request, format-split, deals-split, pod-grouping, imp-flatten-aggregate, filtered-subset, grouped-by-key`) are detected by the structural cues in the patterns reference. Always set `batching.applied_in_order: true`.
2. **`request_body.kind`** — `openrtb2-passthrough` (request marshaled unchanged), `openrtb2-modified` (request copied + mutated then marshaled), or `custom` (a non-OpenRTB struct is marshaled). When `custom`, set `custom_body_type` to the struct name and emit a `multi-file-layout-justified` quirk for the proto file (canonical: mediasquare).
3. **`mutation.entity_strategies`** — map per OpenRTB entity (`Site, App, Source, Imp, Banner, Device, User, Cur, ...`). Strategies: `none, copy-then-mutate, in-place, append-if-missing, immutable-rebuild` (immutable-rebuild appears only on Java). See the patterns reference's mutation table.
4. **`mutation.go_idiom`** — `ptrutil.Clone, shallow-copy, direct-pointer-mutation, none`. `direct-pointer-mutation` is the danger case (mutates framework's request); flag with `provenance.warnings` if found. `mutation.java_idiom` is null on Go specs.
5. **`imp_ext_unmarshal.kind`** — `standard-two-phase` (default — `jsonutil.Unmarshal(imp.Ext, &bidderExt)` then `jsonutil.Unmarshal(bidderExt.Bidder, &impExt)`), `direct` (skip framework wrapper), `none` (no params), or `custom`. Set `mechanism_go: jsonutil-two-phase` for the canonical case; `null` for `direct`/`none`. Set `target_type` to the imp ext struct (`openrtb_ext.ExtImpKobler`); set `wrapper_type` only on `direct`.
6. **`endpoint_resolution.kind`** + **`mechanism_go`** — see the kind/mechanism cross-table in the patterns reference. Mechanism values: `text/template, macros.NewStringIndexBasedReplacer, net/url, string-concat, null`. Populate `macro_field_set[]` with the subset of `macros.EndpointTemplateParams` 18 fields (canonical list at [../../../review/skills/shared/framework-utilities.md#endpoint-template-macros](../../../review/skills/shared/framework-utilities.md#endpoint-template-macros)) actually substituted; `template_params_struct_field_count` records `len(macro_field_set)`.
7. **`helpers[]`** — every unexported function defined alongside the adapter (excluding the implementation methods). Record `name` and `signature`.
8. **`headers_constructed.*`** — when `MakeRequests` constructs headers beyond framework defaults. Set `pre_built_in_constructor: true` when a header is pre-computed in the constructor (rare on Go; Java pattern); else false. `per_request_dynamic: true` when headers are computed per-request. `custom_headers[]` lists the literal headers added. `authentication_kind: none | basic-auth | bearer-token | hmac-digest | custom`. `authentication_input[]` lists field paths the auth value derives from.

   **ADR-007 F2 (`language_stamped_headers[]`)**: set `language_stamped: true` and populate `language_stamped_headers[]` with `{ name, go_value, java_value, rationale }` per item when the adapter emits a header whose VALUE differs by language. Master sample: `freewheelssp` emits `Componentid: prebid-go` (Go) ↔ `prebid-java` (Java) — same header name, different value, byte-asymmetric outbound. Both sides record the same `language_stamped_headers[]` (per-side spec carries the full cross-language pair so cross-language consumers can diff). One-sided header additions (Go emits a header Java doesn't, or vice versa) are NOT F2 — record them as quirks instead per ADR-007's footnote on one-sided header mutations.

### Step 8 — Classify `code.make_bids.*`

Locate `func (a [*]adapter) MakeBids(...)`. Apply rules:

1. **`response_type`** — `openrtb2.BidResponse` (canonical) or `custom` with `custom_response_type` populated.
2. **`http_status_handling.kind`** — `canonical-go-helpers` (uses `adapters.IsResponseStatusCodeNoContent` + `adapters.CheckResponseStatusCodeForErrors`) or `legacy-raw-go` (direct `responseData.StatusCode == http.StatusNoContent` / `!= http.StatusOK`) or `custom`. See [../shared/behavior-taxonomy.md#code-make_bids-http_status_handling-kind](../shared/behavior-taxonomy.md#code-make_bids-http_status_handling-kind).
3. **`application_status_handling.kind`** — `none` default; `retcode-field` when adapter checks an in-body status (canonical: huaweiads). Populate `field, success_codes, error_codes` when `retcode-field`.
4. **`bid_type_resolution.method_chain[]`** — ordered chain. Each step `{ method, field?, hardcoded_value?, fallback_action }`. Method values per [../shared/behavior-taxonomy.md#code-make_bids-bid_type_resolution-method_chain](../shared/behavior-taxonomy.md#code-make_bids-bid_type_resolution-method_chain). `default_value` populated when the last step's `fallback_action: return-default`. `multi_format_detection: strict | lenient | none`.
5. **`bid_pointer_pattern`** — cross-language enum (`indexed-iteration | pointer-iteration | flatten-streams`); `flatten-streams` is Java-only.
6. **`bid_pointer_go_sibling`** — `indexed-seatbid` (when adapter ranges over `response.SeatBid` indexed) or `range-value-pointer` (ranges over values with pointer indexing). See [references/adapter-code-patterns.md](references/adapter-code-patterns.md#bid-pointer-go-sibling-detection).
7. **`currency_overwrite_safety`** — `guarded` (assigns `bidResponse.Currency = response.Cur` only when non-empty), `unguarded` (unconditional assignment from possibly-empty `response.Cur`), `unguarded-hardcoded` (assigns a literal like `"USD"`), `passthrough-from-response` (uses `response.Cur` to construct typed bid metadata), `none` (no `bidResponse.Currency` assignment). Emit an `unguarded-currency-overwrite` quirk when `unguarded` (canonical: optidigital).

### Step 9 — Inventory `tests:`

For each fixture path in `inputs.files.test_fixtures.*`:

1. Test root directory: parse the path's `{xyz}test` (or `{xyz}/test`, `{xyz}/test-extrainfo`) segment. Set `tests.test_root_directory` to that segment.
2. `tests.go_directory_naming`:
   - `canonical` — root is `{xyz}test` (no separator).
   - `legacy-test` — root is `{xyz}/test` (separator).
   - `custom` — anything else (msft uses both `test/` and `test-extrainfo/`); REQUIRES a quirk entry.
3. For each fixture file:
   - In `count-only` mode (default): `{ filename, sha256, bytes }`.
   - In `summary` mode: + extracted media types per fixture (parse `mockBidRequest.imp[].{banner,video,native,audio}`) and HTTP status codes.
   - In `verbatim` mode: + full JSON body inline.
4. Group by subdirectory: `exemplary, supplemental, amp, video, videosupplemental`. Set `integration: []` (Java-only field — empty on Go).
5. Cross-check `_test.go` runner:
   - `uses_canonical_harness: true` if test runner calls `adapterstest.RunJSONBidderTest`. False if it imports `adapterstest.OrtbMockService`/`BidOnTags`/`SampleBid`/`VerifyStringValue` instead — emit `legacy-test-helpers-imported` quirk + `provenance.warnings` entry (Validation Rule R10).
   - Detect `bidder-constant-mismatch` (Validation Rule R7): the constant passed to `Builder()` in the test runner must match `openrtb_ext.Bidder{Xyz}`. Mismatch (kobler_test.go calls Builder with `BidderKargo`) emits a quirk + `provenance.warnings` entry.

### Step 10 — Emit `quirks[]`

For each unclassifiable pattern observed in any of Steps 4–9, add an entry to `quirks[]`. Every `custom` value in an enumerated field REQUIRES a quirk entry (Validation Rule R3). The `edge_case_taxon` MUST be picked from the registry at [../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry](../shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry).

For the comprehensive emission rules with real-adapter examples and decision logic, see [references/quirk-catalog.md](references/quirk-catalog.md). That file documents when to emit each registered taxon, with file:line citations and the spec field that cannot capture the pattern.

### Step 11 — Populate `cross_language.go_specific_concerns[]` and stub `java_specific_concerns[]`

Densely populate `go_specific_concerns[]` with free-text observations a Java porter must address. Examples (verbatim from kobler.golden.spec.yaml):

- value-receiver methods (`func (a adapter) MakeRequests`) when reviewers prefer pointer receivers
- shallow-copy semantics that share backing-array memory across the function boundary
- per-imp index-only branching (e.g., reading `imp.ext.test` only at `i == 0`)
- package-level constants that should be config fields
- legacy raw status checks that pre-date the canonical helpers

Set `java_specific_concerns: []` (this skill does not read Java).

Also populate `cross_language.port_concerns` flags this skill can determine:

- `multi_file_layout` — from Step 1 (count of non-test `.go` files > 1).
- `package_directory_mismatch` — from Step 3.
- `custom_unmarshaljson_present` — true when any type in this adapter's package defines `UnmarshalJSON` (canonical: appnexus keywords). Triggers a quirk with `edge_case_taxon: <taxon>` per the catalog.
- `mutation_idiom_divergence` — `true` when `mutation.go_idiom != none` AND the corresponding Java-side idiom would be `lombok-tobuilder`. Conservative heuristic: `true` whenever Go mutates request entities at all (matches kobler precedent). The orchestrator may downgrade to `false` after merging the Java spec (out of this skill's scope).

The other `port_concerns` flags (`aliases_inverted, yaml_unification`) are populated by sibling skills.

## Edge case mapping (the 17 Go cases)

Each Go edge case from the plan maps to specific spec fields owned by this skill. No edge case falls through to `quirks` unless it is genuinely unclassifiable. Table:

| # | Edge case | Owned by this skill? | Captured by |
|---|---|---|---|
| 1 | Package name ≠ directory name | yes | `code.package_directory_mismatch`, `code.package_or_class`, `code.directory_name` |
| 2 | Adapter struct identifier varies | yes | `code.adapter_struct.{type_name, type_visibility}` |
| 3 | Test directory naming exceptions | yes | `tests.test_root_directory`, `tests.go_directory_naming` |
| 4 | Multi-file Go layout | yes | `code.file_layout.kind`, `cross_language.port_concerns.multi_file_layout` |
| 5 | Custom request body (non-OpenRTB) | yes | `code.make_requests.request_body.{kind, custom_body_type}` + quirk |
| 6 | Custom response unmarshal | yes | `code.make_bids.{response_type, custom_response_type}` + quirk |
| 7 | Intentional JSON key style mismatch (msft `pubclick`) | partial | quirk `json-key-style-mismatch` (the field-level `notes` lives on `params.ext_struct.fields[].notes`, owned by `read-bidder-params`) |
| 8 | Hardcoded constants (kobler dev-endpoint) | yes | quirk `hardcoded-config-as-anti-pattern` |
| 9 | Custom UnmarshalJSON (appnexus keywords) | yes | `cross_language.port_concerns.custom_unmarshaljson_present` + quirk; the field-level shape detail belongs to `read-bidder-params.ext_pojo_construction.custom_unmarshal` |
| 10 | Three endpoint construction routes | shared | `code.make_requests.endpoint_resolution.{kind, mechanism_go, macro_field_set}` (this skill) + `bidder_info.endpoint_construction.kind` (read-bidder-info) |
| 11 | Request grouping by various keys | yes | `code.make_requests.batching.rules[]` |
| 12 | Status-code handling diverges | yes | `code.make_bids.http_status_handling.kind` |
| 13 | Currency-overwrite safety | yes | `code.make_bids.currency_overwrite_safety` |
| 14 | Shallow-copy correctness | yes | `code.make_requests.mutation.entity_strategies` + `mutation.go_idiom` |
| 15 | Per-seat-bid pointer pattern | yes | `code.make_bids.bid_pointer_pattern`, `bid_pointer_go_sibling` |
| 16 | macros.EndpointTemplateParams field usage | yes | `code.make_requests.endpoint_resolution.{macro_field_set, template_params_struct_field_count}` |
| 17 | JSON Schema combinators | no | owned by `read-bidder-params.params.schema_interpretation.combinators_used` |

## Quirks emission

A quirk is a structured free-text bucket entry with a required taxon from the closed registry. Each quirk: `{ id, file, summary, edge_case_taxon }`. See [references/quirk-catalog.md](references/quirk-catalog.md) for the full when-to-emit decision matrix with real-adapter file:line examples for every registered taxon.

The catalog covers every registered taxon; this skill emits quirks under: `hardcoded-config-as-anti-pattern, json-key-style-mismatch (test side), multi-file-layout-justified, legacy-go-pattern-pre-1.22, incomplete-classification, legacy-encoding-json-direct-usage, legacy-test-helpers-imported, unguarded-currency-overwrite, hardcoded-bid-type, bidder-constant-mismatch (test side), legacy-impext-naming (file-side observation; the type-name observation is shared with read-bidder-params)`. The remaining taxa belong to sibling skills.

## Verification

The two canonical golden specs serve as proof-of-concept outputs:

- [../../test-fixtures/optidigital.golden.spec.yaml](../../test-fixtures/optidigital.golden.spec.yaml) — clean baseline, single-file, banner-only, hardcoded `BidTypeBanner`. This skill owns lines covering `code.*` (lines 128–202), `tests.*` (lines 203–234), `cross_language.go_artifacts/java_artifacts/port_concerns` (lines 286–303), and the `legacy-impext-naming, hardcoded-banner-bid-type, unguarded-currency-overwrite` quirks (lines 272–284).
- [../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml) — currency conversion, dev-prod toggle, two test-side `bidder-constant-mismatch` warnings. This skill owns `code.*` (lines 108–196), `tests.*` (lines 198–250), `cross_language.go_artifacts/java_artifacts/port_concerns/go_specific_concerns/java_specific_concerns/reviewer_cohort.go` (lines 308–350 minus the orchestrator-owned `port_lineage` block), and the four quirks (lines 290–306) `bidder-constant-mismatch-test`, `bidder-constant-mismatch-params-test`, `hardcoded-dev-endpoint`, `dev-prod-toggle-via-imp-ext-test-flag`.

A reader following this SKILL.md should produce a spec that matches these goldens byte-for-byte modulo `provenance.read.timestamp_utc`. Validation Rule R4 (round-trip determinism) is enforced by the orchestrator's CI harness.

## Cross-skill references (read-only, do not duplicate)

This skill links to the existing review/ master-truth references rather than re-listing canonical helpers:

- **[../../../review/skills/shared/framework-utilities.md](../../../review/skills/shared/framework-utilities.md)** — module path, `EndpointTemplateParams` 18-field list, `errortypes.*` constructors, `jsonutil.*` helpers, `adapters.*` canonical helpers, anti-pattern list, test harness contract. This skill's classification rules cite it; do not copy.
- **[../../../review/skills/adapter-code-pr-review/SKILL.md](../../../review/skills/adapter-code-pr-review/SKILL.md)** — review-time workflows for the same code (Builder, MakeRequests, MakeBids, etc.). The review skill prescribes; this skill describes.
- **[../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md](../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md)** — adapter code patterns (Builder, MakeRequests, MakeBids, helpers). This skill's [adapter-code-patterns.md](references/adapter-code-patterns.md) adds READ-TIME classification rules on top.
- **[../shared/adapter-spec.md](../shared/adapter-spec.md)** — canonical schema + Kobler worked example (Go and Java side by side).
- **[../shared/behavior-taxonomy.md](../shared/behavior-taxonomy.md)** — every enumerated value with cross-references back to the review/ master-truth.
- **[../shared/port-translation-rules.md](../shared/port-translation-rules.md)** — 46 Go↔Java port rules; the `cross_language.go_specific_concerns[]` text should reference rule numbers when applicable.

## Sources

- Plan: (Claude Code planning artifact).
- Schema: [../shared/adapter-spec.md](../shared/adapter-spec.md).
- Taxonomy: [../shared/behavior-taxonomy.md](../shared/behavior-taxonomy.md).
- Port-translation rules: [../shared/port-translation-rules.md](../shared/port-translation-rules.md).
- Review-skill master-truth: [../../../review/skills/adapter-code-pr-review/SKILL.md](../../../review/skills/adapter-code-pr-review/SKILL.md), [../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md](../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md), [../../../review/skills/shared/framework-utilities.md](../../../review/skills/shared/framework-utilities.md).
- Golden specs: [../../test-fixtures/optidigital.golden.spec.yaml](../../test-fixtures/optidigital.golden.spec.yaml), [../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml).
- `prebid/prebid-server` master at v4.1.0 (commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` as of 2026-04-27).
