# Adapter Code Patterns (read-time classification)

Read-time classification rules that map Go source-code shapes to Adapter Specification enum values. The master-truth canonical helpers (`EndpointTemplateParams` 18-field list, `errortypes.*` constructors, `jsonutil.*` helpers, `adapters.*` status helpers) are documented at [../../../../review/skills/shared/framework-utilities.md](../../../../review/skills/shared/framework-utilities.md) — this file does NOT re-list them. The review-time prescriptions for the same code live at [../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md](../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md).

This file is the read-time companion: which structural cue maps to which spec enum value. It is consumed by `read-adapter-code/SKILL.md` Steps 5–8.

---

## Adapter struct shapes

The struct identifier varies across adapters. Three observed shapes:

| Identifier | Visibility | When | Spec output |
|---|---|---|---|
| `adapter` | unexported | Default for new adapters (kobler, optidigital, generic). | `code.adapter_struct.{type_name: adapter, type_visibility: unexported}` |
| `TtxAdapter` | exported | Legacy: 33across uses an exported struct because of an early-PBS pattern. | `{type_name: TtxAdapter, type_visibility: exported}` — emit a `legacy-go-pattern-pre-1.22` quirk |
| `adkernelAdapter` | unexported | Bidder-name-prefixed unexported variant (adkernel). | `{type_name: adkernelAdapter, type_visibility: unexported}` |

**Detection rule**: locate the type that the `Builder` function returns (look for `bidder := &<TypeName>{...}` or `return &<TypeName>{...}`). Record the type name verbatim and its visibility (lowercase first char → unexported, uppercase → exported).

**Field extraction**: fields are recorded as `{ name: <fieldName>, type: <fieldType> }`. Pointer types record as `*Type` (e.g., `*template.Template` for adapters that store a parsed template; canonical: adagio). Map types record as `map[K]V`. Empty struct field lists are valid (rare).

For canonical struct rules (unexported, configuration-only, no request-scoped state), see [../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md#adapter-struct-pattern](../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md#adapter-struct-pattern).

---

## Builder canonical signature

The canonical signature is documented in master-truth at [../../../../review/skills/shared/framework-utilities.md#builder-function-signature](../../../../review/skills/shared/framework-utilities.md#builder-function-signature):

```go
func Builder(bidderName openrtb_ext.BidderName, config config.Adapter, server config.Server) (adapters.Bidder, error)
```

Read-time classification:

| Spec field | Signal |
|---|---|
| `signature_canonical: true` | Parameter list matches exactly: `(openrtb_ext.BidderName, config.Adapter, config.Server) (adapters.Bidder, error)`. Parameter NAMES are not load-bearing; types are. |
| `signature_canonical: false` | Any deviation; emit a free-text quirk explaining the deviation (rare in master). |
| `extra_adapter_info_used: true` | Body references `config.ExtraAdapterInfo`. |
| `template_parsed_at_build: true` | Body invokes `template.New(...).Parse(...)` OR `macros.NewStringIndexBasedReplacer(...)`. The latter is the canonical helper; the former pre-dates it. |
| `errors_returned[]` | Each non-nil return path's error category. Catalog: `url_parse_error` (when `url.Parse` fails), `template_parse_error` (template parse), `extra_info_unmarshal_error` (jsonutil.Unmarshal of ExtraAdapterInfo), `validation_error` (Builder validates a config field — anti-pattern, flag with INFO quirk). Empty `errors_returned: []` when Builder cannot fail. |

Builder error paths typically arise from:
1. Endpoint URL parsing (`url.Parse(config.Endpoint)`).
2. Template parsing (`template.New(...).Parse(config.Endpoint)`).
3. ExtraAdapterInfo unmarshal (`jsonutil.Unmarshal([]byte(config.ExtraAdapterInfo), &x)`).

The kobler adapter has no error paths (`errors_returned: []`); the adagio adapter has `errors_returned: [template_parse_error]`.

---

## MakeRequests classification

### `batching.rules[]` rule kinds

Refactored from scalar enum to ordered list per [../../shared/behavior-taxonomy.md#code-make_requests-batching-rules](../../shared/behavior-taxonomy.md#code-make_requests-batching-rules). Composability: rules are applied in order; multiple rules may co-exist.

| Rule kind | Detection cue | Carries |
|---|---|---|
| `single-batched` | One `RequestData` constructed and returned with `request.Imp` passed unchanged. Default. | none |
| `per-imp` | Loop `for i := range request.Imp { ... requestData = append(...) }` producing N RequestData. | none |
| `max-imps-per-request` | Slicing `request.Imp` by a constant chunk size (`for i := 0; i < len(imps); i += N`). | `max: <int>` |
| `format-split` | Outer loop over `[]openrtb_ext.BidType{BidTypeBanner, BidTypeVideo, ...}` filtering imps by media type. | `formats: []` |
| `deals-split` | Outer loop over `imp.PMP.Deals[]` producing one request per deal. | `deal_field: imp.pmp.deals[].id` |
| `pod-grouping` | `strings.SplitN(imp.ID, "_", 2)[0]` used as a grouping key. | `key: imp.id-prefix-before-underscore` |
| `imp-flatten-aggregate` | Multiple imps coalesce into one `custom` body type (e.g., a `codes[]` array). | `custom_body_type: <type>` |
| `filtered-subset` | Imps filtered by a bidder-specific predicate before batching (e.g., `if imp.Ext == nil { continue }`). | `predicate: <free-text>` |
| `grouped-by-key` | Group imps by an arbitrary publisher-id / account-id key. | `key: <field-path>`, `group_id_construction: <expr>` |
| `custom` | Anything else. REQUIRES a quirk entry. | n/a |

When two rules co-exist (e.g., appnexus emits `pod-grouping` THEN `max-imps-per-request: 10`), the spec lists both with `applied_in_order: true` and the order matters: grouping happens first, then size-split each group.

### `request_body.kind`

| Value | Detection cue |
|---|---|
| `openrtb2-passthrough` | `requestJSON, err := jsonutil.Marshal(request)` with no prior mutation of `request`. |
| `openrtb2-modified` | `request` (or a copy) is mutated before marshal. Look for assignments to `request.X`, `requestCopy := *request`, or `sanitizedRequest := sanitizeRequest(*request)`. |
| `custom` | A bidder-specific struct is marshaled (not `openrtb2.BidRequest`). REQUIRES a quirk and `custom_body_type: <struct-name>`. |

### `mutation.entity_strategies` (cross-language)

Per [../../shared/behavior-taxonomy.md#code-make_requests-mutation](../../shared/behavior-taxonomy.md#code-make_requests-mutation). Strategies for each OpenRTB entity:

| Strategy | Go detection cue |
|---|---|
| `none` | Entity is not assigned. |
| `copy-then-mutate` | `<entityCopy> := *<entity>; <entityCopy>.X = ...; request.<Entity> = &<entityCopy>` (canonical: optidigital site mutation). |
| `in-place` | Direct pointer mutation: `<entity>.X = ...` without prior copy (kobler `device.IP = ""`). May write back through to framework when the slice/pointer is shared — flag as `direct-pointer-mutation` go_idiom. |
| `append-if-missing` | `if !slices.Contains(...) { <slice> = append(<slice>, ...) }` (kobler `Cur` field). |
| `immutable-rebuild` | NOT used in Go (Java-only `lombok-tobuilder`). |

Track per OpenRTB entity name: `Site, App, Source, Imp, Banner, Device, User, Cur, Regs, Publisher`.

### `mutation.go_idiom`

| Idiom | Detection cue |
|---|---|
| `ptrutil.Clone` | Adapter calls `ptrutil.Clone(...)` on any pointer entity. Recommended for deep-copy of nested pointer fields. |
| `shallow-copy` | Adapter dereferences a pointer (`*entity`) to copy a value, mutates the copy, then re-points (`request.Entity = &entityCopy`). Most common pattern. |
| `direct-pointer-mutation` | Adapter mutates through the pointer directly without copying first. NOT recommended — emit a `provenance.warnings` entry. |
| `none` | Adapter does not mutate. Set when `mutates_request: false`. |

`mutation.java_idiom` is always `null` on Go-source specs.

### `imp_ext_unmarshal.kind`

| Kind | Go detection cue |
|---|---|
| `standard-two-phase` | `jsonutil.Unmarshal(imp.Ext, &bidderExt)` (where `bidderExt` is `adapters.ExtImpBidder`) followed by `jsonutil.Unmarshal(bidderExt.Bidder, &impExt)`. The default. |
| `direct` | `jsonutil.Unmarshal(imp.Ext, &<customWrapper>)` where the wrapper is a bidder-specific type, NOT `adapters.ExtImpBidder`. Set `wrapper_type` to that type's name (canonical: appnexus uses `appnexusExtImp`). |
| `none` | No `imp.Ext` unmarshal at all (no params declared). |
| `custom` | Anything else. REQUIRES a quirk entry. |

`mechanism_go: jsonutil-two-phase` for the canonical case; `null` for `direct`/`none`. `mechanism_java` is always `null` on Go-source specs. `target_type` records the bidder-specific type (`openrtb_ext.ExtImpKobler`); `wrapper_type` records the wrapper for the `direct` case.

### `endpoint_resolution.kind` and `mechanism_go` cross-table

The kind is semantic (cross-language); the mechanism is Go-specific implementation. Per [../../shared/behavior-taxonomy.md#code-make_requests-endpoint_resolution](../../shared/behavior-taxonomy.md#code-make_requests-endpoint_resolution).

| `kind` | When | Typical `mechanism_go` |
|---|---|---|
| `static` | Literal URL stored in adapter struct, no substitution. | `null` |
| `single-token-substitution` | One macro field (e.g., `{{.AccountID}}`). | `text/template` (parsed at Builder) or `string-concat` (one-off `strings.Replace`). |
| `multi-token-substitution` | Multiple macros (e.g., rubicon `{{.AccountID}}` + `{{.ZoneID}}`). | `text/template` or `macros.NewStringIndexBasedReplacer`. |
| `query-parameter-augmentation` | Endpoint URL has query params appended at request time (appnexus `member_id`). | `net/url` |
| `runtime-region-selection` | Endpoint chosen at request time based on `device.geo.country` or similar (huaweiads). | `string-concat` (typically a switch statement) |
| `deploy-time-token` | Non-Go-template placeholder (rubicon `#{REGION}#`) substituted by the operator pre-deployment. | `null` (no runtime mechanism); surfaces under `deploy_time_tokens[]`. |
| `dev-prod-toggle` | Endpoint chosen between two literal URLs based on a request-time flag (kobler). | `string-concat` (no template engine) |
| `custom` | Anything else. REQUIRES a quirk entry. | language-specific |

`macro_field_set` lists the subset of `macros.EndpointTemplateParams` 18 fields actually substituted (the canonical 18-field list is at [../../../../review/skills/shared/framework-utilities.md#endpoint-template-macros](../../../../review/skills/shared/framework-utilities.md#endpoint-template-macros)). `template_params_struct_field_count` records `len(macro_field_set)`.

### `currency.{converts_currency, conversion_helper, overwrite_safety}` (in `make_requests`)

Note the spec field for currency conversion in MakeRequests is captured under `currency_conversion` at the top level, NOT under `make_requests.currency`. This skill should:

- Set `currency_conversion.used: true` when adapter calls `reqInfo.ConvertCurrency(...)`.
- Set `currency_conversion.helper.go_signature: "reqInfo.ConvertCurrency(value, from, to) (float64, error)"`.
- Set `currency_conversion.injection: function-arg`.
- Set `currency_conversion.bid_request_passed_for_context: false` (Go's `reqInfo.ConvertCurrency` does NOT take bidRequest — Java's does; this is the canonical port-fidelity divergence captured by Rule 32 at [../../shared/port-translation-rules.md#rule-32-reqinfoconvertcurrency-vs-currencyconversionserviceconvertcurrency](../../shared/port-translation-rules.md#rule-32-reqinfoconvertcurrency-vs-currencyconversionserviceconvertcurrency)).

---

## MakeBids classification

### `response_type` and `custom_response_type`

| Value | Detection cue |
|---|---|
| `openrtb2.BidResponse` | `var response openrtb2.BidResponse; jsonutil.Unmarshal(responseData.Body, &response)`. Default. |
| `custom` | A bidder-specific response type is unmarshaled instead. REQUIRES a quirk and `custom_response_type: <type-name>` (canonical: mediasquare `mediasquareResponse`). |

### `http_status_handling.kind`

| Value | Detection cue |
|---|---|
| `canonical-go-helpers` | Adapter calls `adapters.IsResponseStatusCodeNoContent(responseData)` AND `adapters.CheckResponseStatusCodeForErrors(responseData)`. The recommended pattern (introduced ~v3.30). |
| `legacy-raw-go` | Adapter directly checks `responseData.StatusCode == http.StatusNoContent` AND/OR `responseData.StatusCode != http.StatusOK`. Pre-canonical-helper pattern. |
| `custom-status-checks` | Adapter implements bespoke status checks beyond 204/non-2xx (e.g., specific 4xx codes treated as no-bid). |
| `framework-default` / `framework-default-plus-empty-seatbid-shortcircuit` | Java-only enums. Not emitted by this skill. |
| `custom` | Anything else. REQUIRES a quirk entry. |

The canonical helpers are documented at [../../../../review/skills/shared/framework-utilities.md#framework-helper-functions](../../../../review/skills/shared/framework-utilities.md#framework-helper-functions).

### `application_status_handling`

Captures application-layer status indicators in the response body (distinct from HTTP status). Per [../../shared/behavior-taxonomy.md#code-make_bids-application_status_handling](../../shared/behavior-taxonomy.md#code-make_bids-application_status_handling).

| Kind | Detection cue |
|---|---|
| `none` | No body-status check found. Default. |
| `retcode-field` | Adapter checks a `retcode` (or similar) field in the response body. Populate `field, success_codes, error_codes`. Canonical: huaweiads. |
| `custom-body-flag` | Non-standard body flag check. REQUIRES a quirk entry. |

### `bid_type_resolution.method_chain[]`

Refactored from scalar to ordered chain per [../../shared/behavior-taxonomy.md#code-make_bids-bid_type_resolution-method_chain](../../shared/behavior-taxonomy.md#code-make_bids-bid_type_resolution-method_chain). Each step `{ method, field?, hardcoded_value?, fallback_action }`. `fallback_action: next | return-default | throw`.

| Method | Detection cue |
|---|---|
| `by-imp-mediatype` | Function that loops over `imps`, matches `bid.ImpID == imp.ID`, then checks `imp.Banner != nil` / `imp.Video != nil` / `imp.Native != nil` / `imp.Audio != nil`. Default first step in chains. |
| `by-bid-mtype` | `switch bid.MType { case openrtb2.MarkupBanner: ... case openrtb2.MarkupVideo: ... }`. Modern OpenRTB 2.6 pattern. |
| `by-bid-ext-typed-field` | Adapter unmarshals `bid.Ext` into a typed struct and reads a typed field (e.g., `bidExt.Prebid.Type`, `bidExt.Appnexus.BidAdType`). Populate `field` with the dotted path (e.g., `bid.ext.prebid.type`). |
| `by-imp-id-suffix` | Parses a suffix on `imp.ID` to disambiguate multi-format imps (e.g., trailing `_b` or `_v`). |
| `imp-prefix-lookup` | Uses a prefix on `imp.ID` (typically before underscore) to look up the original imp. |
| `by-response-payload-shape` | Inspects the response payload structure (e.g., `bid.Video != nil`). Used with `response_type: custom`. |
| `hardcoded` | Returns a fixed `BidType` regardless of bid/imp. Populate `hardcoded_value: BidTypeBanner` (or similar). REQUIRES a quirk entry — emit `hardcoded-bid-type` taxon. |
| `custom` | Anything else. REQUIRES a quirk entry. |

`default_value` is populated when the last step's `fallback_action: return-default` — captures the literal type returned (e.g., `banner`).

`multi_format_detection`:
- `strict` — when imp has multiple media types and bid lacks `mtype`/typed-ext, throw.
- `lenient` — fall back to default media type or first non-nil imp media type.
- `none` — adapter does not handle multi-format imps.

### `bid_pointer_pattern` and `bid_pointer_go_sibling` detection

The cross-language `bid_pointer_pattern` field captures the iteration shape; the `bid_pointer_go_sibling` field captures Go-specific idiom variation.

| `bid_pointer_pattern` | Detection cue |
|---|---|
| `indexed-iteration` | `for i := range response.SeatBid { ... for j := range response.SeatBid[i].Bid { ... &response.SeatBid[i].Bid[j] ... } }` — index-based access. |
| `pointer-iteration` | `for _, seatBid := range response.SeatBid { ... for i := range seatBid.Bid { ... &seatBid.Bid[i] ... } }` — value+pointer-index variant (canonical: optidigital). |
| `flatten-streams` | Java-only. Never emitted by this skill. |

| `bid_pointer_go_sibling` | Detection cue |
|---|---|
| `indexed-seatbid` | Both loops use indexed access. |
| `range-value-pointer` | Outer loop uses value (`for _, seatBid := range`) and inner loop uses index (`for i := range seatBid.Bid`). Optidigital and kobler both use this. |

The bid pointer safety rule (`&seatBid.Bid[i]` instead of `&bid` from a loop variable) is a review-time check at [../../../../review/skills/adapter-code-pr-review/SKILL.md#workflow-makebids-changed](../../../../review/skills/adapter-code-pr-review/SKILL.md#workflow-makebids-changed) (rule 7) — read-time only records the pattern.

### `currency_overwrite_safety`

| Value | Detection cue |
|---|---|
| `guarded` | `if response.Cur != "" { bidResponse.Currency = response.Cur }` — checks non-empty before assignment. |
| `unguarded` | `bidResponse.Currency = response.Cur` without a non-empty check. Emit an `unguarded-currency-overwrite` quirk (canonical: optidigital). |
| `unguarded-hardcoded` | `bidResponse.Currency = "USD"` (or similar literal) regardless of upstream. |
| `passthrough-from-response` | The adapter does NOT assign `bidResponse.Currency` directly but uses `response.Cur` to construct typed bid metadata (e.g., `bidderResponse.Bids = append(..., &TypedBid{... Currency: response.Cur})`). Canonical: kobler. |
| `none` | No `bidResponse.Currency` assignment found. The framework defaults the currency to USD. |

### `iab_category_storage` (when adapter performs category lookup)

Most Go adapters do NOT lookup IAB categories. When they do (canonical: msft):

- `storage_kind: go-data-table` — co-located Go data file (e.g., `iab_categories.go`).
- `go_data_file: adapters/msft/iab_categories.go` — full path.
- `table_size: <int>` — number of entries.
- `injection: static-init` — typically a package-level `var iabCategories = map[string]string{ ... }`.
- `yaml_field: null` — Java-only.

If no lookup is performed: `storage_kind: none` and all other fields null (default).

---

## Cross-references

- Master-truth helpers + 18-field macro list + error type taxonomy + anti-pattern list: [../../../../review/skills/shared/framework-utilities.md](../../../../review/skills/shared/framework-utilities.md).
- Review-time prescriptions for the same code: [../../../../review/skills/adapter-code-pr-review/SKILL.md](../../../../review/skills/adapter-code-pr-review/SKILL.md), [../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md](../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md).
- Canonical schema with worked Kobler example: [../../shared/adapter-spec.md](../../shared/adapter-spec.md).
- Enum source-of-truth: [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md).
- Cross-language port translation: [../../shared/port-translation-rules.md](../../shared/port-translation-rules.md).
- File role classification rules: [file-role-heuristics.md](file-role-heuristics.md).
- Quirk emission decision matrix: [quirk-catalog.md](quirk-catalog.md).

---

## Sources

- `prebid/prebid-server` master at v4.1.0 (commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` as of 2026-04-27):
  - `adapters/kobler/kobler.go:23` — `const devBidderEndpoint = "..."` (hardcoded-config-as-anti-pattern).
  - `adapters/kobler/kobler.go:163` — `func sanitizeRequest(request openrtb2.BidRequest) *openrtb2.BidRequest` (value-receiver, shallow-copy idiom).
  - `adapters/kobler/kobler.go:104-112` — direct `responseData.StatusCode == http.StatusNoContent` checks (legacy-raw-go).
  - `adapters/optidigital/optidigital.go` — `bidResponse.Currency = response.Cur` unguarded; `BidTypeBanner` hardcoded; range-value-pointer.
  - `adapters/33across/` — package `ttx` (package-directory mismatch, exported struct `TtxAdapter`).
  - `adapters/mediasquare/` — multi-file layout, custom request body type `mediasquareRequest`.
  - `adapters/msft/` — multi-file with `iab_categories.go` data table, `test/` and `test-extrainfo/` legacy directory naming.
  - `adapters/appnexus/` — custom UnmarshalJSON on keywords field, max-imps-per-request + pod-grouping composed batching.
- Sibling shared file: [../../shared/adapter-spec.md](../../shared/adapter-spec.md).
- Sibling shared file: [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md).
- Sibling shared file: [../../shared/port-translation-rules.md](../../shared/port-translation-rules.md).
- Review-skill master-truth: [../../../../review/skills/shared/framework-utilities.md](../../../../review/skills/shared/framework-utilities.md), [../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md](../../../../review/skills/adapter-code-pr-review/references/adapter-code-index.md).
